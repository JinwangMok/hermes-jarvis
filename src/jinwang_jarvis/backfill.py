from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Callable

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig
from .mail import (
    choose_sent_folder,
    normalize_envelope,
    parse_folder_list_table,
    _append_message_rows,
    _load_json_output,
)

WINDOWS = {
    "1w": timedelta(days=7),
    "1m": timedelta(days=30),
    "3m": timedelta(days=90),
    "6m": timedelta(days=180),
}
DEFAULT_PAGE_SIZE = 100
MAX_BACKFILL_PAGES = 200


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _normalize_as_of(as_of: datetime | None) -> datetime:
    if as_of is None:
        return _utc_now()
    return as_of.astimezone(UTC).replace(microsecond=0)


def _default_runner(args: list[str]) -> str:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout


def _load_checkpoints(path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _parse_himalaya_date(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fetch_backfill_rows_for_folder(
    *,
    runner: Callable[[list[str]], str],
    account: str,
    folder_kind: str,
    folder_name: str,
    page_size: int,
    start: datetime,
    end: datetime,
) -> list[dict]:
    collected: list[dict] = []
    seen_ids: set[str] = set()
    for page in range(1, MAX_BACKFILL_PAGES + 1):
        args = [
            "himalaya",
            "envelope",
            "list",
            "-a",
            account,
        ]
        if folder_kind == "sent":
            args.extend(["--folder", folder_name])
        args.extend([
            "--page",
            str(page),
            "--page-size",
            str(page_size),
            "--output",
            "json",
        ])
        try:
            page_rows = _load_json_output(runner(args))
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "") if hasattr(exc, "stderr") else ""
            if "out of bounds" in stderr.lower() or "out of bounds" in str(exc).lower():
                break
            raise
        except Exception as exc:
            if "out of bounds" in str(exc).lower():
                break
            raise
        if not page_rows:
            break

        page_in_window = 0
        oldest_dt: datetime | None = None
        for item in page_rows:
            normalized = normalize_envelope(account=account, folder_kind=folder_kind, folder_name=folder_name, envelope=item)
            sent_dt = _parse_himalaya_date(normalized.get("date"))
            if sent_dt is None:
                continue
            oldest_dt = sent_dt if oldest_dt is None else min(oldest_dt, sent_dt)
            if sent_dt < start:
                continue
            if sent_dt > end:
                continue
            if normalized["message_id"] in seen_ids:
                continue
            seen_ids.add(normalized["message_id"])
            collected.append(normalized)
            page_in_window += 1

        if oldest_dt is not None and oldest_dt < start and page_in_window == 0:
            break
    return collected


def _collect_window_messages(
    config: PipelineConfig,
    *,
    runner: Callable[[list[str]], str],
    start: datetime,
    end: datetime,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[dict], dict[str, dict]]:
    all_rows: list[dict] = []
    account_summary: dict[str, dict] = {}
    for account in config.accounts:
        folders = parse_folder_list_table(runner(["himalaya", "folder", "list", "-a", account]))
        sent_folder = choose_sent_folder(account, folders, config.sent_folder_overrides)
        inbox_rows = _fetch_backfill_rows_for_folder(
            runner=runner,
            account=account,
            folder_kind="inbox",
            folder_name="INBOX",
            page_size=page_size,
            start=start,
            end=end,
        )
        sent_rows = _fetch_backfill_rows_for_folder(
            runner=runner,
            account=account,
            folder_kind="sent",
            folder_name=sent_folder,
            page_size=page_size,
            start=start,
            end=end,
        )
        rows = inbox_rows + sent_rows
        all_rows.extend(rows)
        account_summary[account] = {
            "sent_folder": sent_folder,
            "inbox_count": len(inbox_rows),
            "sent_count": len(sent_rows),
        }
    return all_rows, account_summary


def run_progressive_backfill(
    config: PipelineConfig,
    *,
    as_of: datetime | None = None,
    windows: tuple[str, ...] = ("1w", "1m", "3m", "6m"),
    runner: Callable[[list[str]], str] | None = None,
) -> dict:
    bootstrap_workspace(config)
    end = _normalize_as_of(as_of)
    export_dir = config.workspace_root / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    checkpoints = _load_checkpoints(config.checkpoints_path)
    checkpoints.setdefault("backfill", {})
    results: list[dict] = []
    runner = runner or _default_runner

    for window_name in windows:
        if window_name not in WINDOWS:
            raise ValueError(f"Unsupported backfill window: {window_name}")
        start = end - WINDOWS[window_name]
        start_text = start.isoformat()
        end_text = end.isoformat()
        rows, account_summary = _collect_window_messages(config, runner=runner, start=start, end=end)
        _append_message_rows(config.database_path, rows)
        notes = f"source backfill completed via himalaya pagination for window {window_name}"
        with sqlite3.connect(config.database_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO backfill_runs (
                    window_name, window_start, window_end, status, messages_scanned, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (window_name, start_text, end_text, "completed", len(rows), notes),
            )
            conn.commit()
        artifact_path = export_dir / f"backfill-{window_name}-{end.strftime('%Y%m%dT%H%M%SZ')}.json"
        artifact = {
            "window_name": window_name,
            "window_start": start_text,
            "window_end": end_text,
            "status": "completed",
            "messages_scanned": len(rows),
            "notes": notes,
            "accounts": account_summary,
            "message_ids": [row["message_id"] for row in rows],
        }
        artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        checkpoints["backfill"][window_name] = {
            "window_start": start_text,
            "window_end": end_text,
            "status": "completed",
            "messages_scanned": len(rows),
            "artifact_file": artifact_path.name,
            "source_mode": "himalaya-pagination",
        }
        results.append({**artifact, "artifact_path": artifact_path})

    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"completed_at": end.isoformat(), "runs": results}
