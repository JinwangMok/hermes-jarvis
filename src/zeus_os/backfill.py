from __future__ import annotations

import json
import re
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
WINDOW_PATTERN = re.compile(r"^(?P<count>\d+)(?P<unit>[wm])$")


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


def resolve_window_delta(window_name: str) -> timedelta:
    normalized = window_name.strip().lower()
    if normalized in WINDOWS:
        return WINDOWS[normalized]
    match = WINDOW_PATTERN.match(normalized)
    if not match:
        raise ValueError(f"Unsupported backfill window: {window_name}")
    count = int(match.group("count"))
    unit = match.group("unit")
    if count <= 0:
        raise ValueError(f"Unsupported backfill window: {window_name}")
    if unit == "w":
        return timedelta(days=count * 7)
    if unit == "m":
        return timedelta(days=count * 30)
    raise ValueError(f"Unsupported backfill window: {window_name}")


def _window_sort_key(window_name: str) -> tuple[int, int]:
    normalized = window_name.strip().lower()
    match = WINDOW_PATTERN.match(normalized)
    if not match:
        return (9, 0)
    count = int(match.group("count"))
    unit = match.group("unit")
    return (0 if unit == "w" else 1, count)


def _month_count(window_name: str) -> int | None:
    normalized = window_name.strip().lower()
    match = WINDOW_PATTERN.match(normalized)
    if not match or match.group("unit") != "m":
        return None
    return int(match.group("count"))


def determine_next_backfill_month_window(
    checkpoints: dict,
    *,
    max_months: int = 36,
    step_months: int = 3,
    baseline_months: int = 6,
) -> str | None:
    completed = {
        key.strip().lower()
        for key, payload in (checkpoints.get("backfill") or {}).items()
        if isinstance(payload, dict) and payload.get("status") == "completed"
    }
    for month in range(baseline_months + step_months, max_months + 1, step_months):
        candidate = f"{month}m"
        if candidate not in completed:
            return candidate
    return None


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
        start = end - resolve_window_delta(window_name)
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


def run_next_backfill_step(
    config: PipelineConfig,
    *,
    as_of: datetime | None = None,
    max_months: int = 36,
    step_months: int = 3,
    baseline_months: int = 6,
    runner: Callable[[list[str]], str] | None = None,
) -> dict:
    bootstrap_workspace(config)
    checkpoints = _load_checkpoints(config.checkpoints_path)
    next_window = determine_next_backfill_month_window(
        checkpoints,
        max_months=max_months,
        step_months=step_months,
        baseline_months=baseline_months,
    )
    if next_window is None:
        completed_at = _normalize_as_of(as_of).isoformat()
        completed_windows = sorted((checkpoints.get("backfill") or {}).keys(), key=_window_sort_key)
        return {
            "completed_at": completed_at,
            "next_window": None,
            "executed": False,
            "runs": [],
            "completed_windows": completed_windows,
        }

    end = _normalize_as_of(as_of)
    next_months = _month_count(next_window)
    if next_months is None:
        raise ValueError(f"Expected month window, got {next_window}")
    previous_months = next_months - step_months
    start = end - timedelta(days=next_months * 30)
    slice_end = end - timedelta(days=previous_months * 30)
    runner = runner or _default_runner
    rows, account_summary = _collect_window_messages(config, runner=runner, start=start, end=slice_end)
    _append_message_rows(config.database_path, rows)

    export_dir = config.workspace_root / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    notes = f"incremental 3-month extension completed for {next_window} via himalaya pagination"
    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO backfill_runs (
                window_name, window_start, window_end, status, messages_scanned, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (next_window, start.isoformat(), slice_end.isoformat(), "completed", len(rows), notes),
        )
        conn.commit()

    artifact_path = export_dir / f"backfill-{next_window}-{end.strftime('%Y%m%dT%H%M%SZ')}.json"
    artifact = {
        "window_name": next_window,
        "window_start": start.isoformat(),
        "window_end": slice_end.isoformat(),
        "status": "completed",
        "messages_scanned": len(rows),
        "notes": notes,
        "accounts": account_summary,
        "message_ids": [row["message_id"] for row in rows],
        "incremental_extension": {
            "from_months": previous_months,
            "to_months": next_months,
        },
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoints.setdefault("backfill", {})
    checkpoints["backfill"][next_window] = {
        "window_start": start.isoformat(),
        "window_end": slice_end.isoformat(),
        "status": "completed",
        "messages_scanned": len(rows),
        "artifact_file": artifact_path.name,
        "source_mode": "himalaya-pagination-incremental",
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    updated_checkpoints = _load_checkpoints(config.checkpoints_path)
    return {
        "completed_at": end.isoformat(),
        "next_window": next_window,
        "executed": True,
        "runs": [{**artifact, "artifact_path": artifact_path}],
        "completed_windows": sorted((updated_checkpoints.get("backfill") or {}).keys(), key=_window_sort_key),
    }
