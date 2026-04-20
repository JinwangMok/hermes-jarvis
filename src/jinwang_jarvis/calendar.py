from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig


def build_dedup_key(summary: str | None, start_ts: str | None) -> str:
    normalized_summary = (summary or "").strip().casefold()
    normalized_start = (start_ts or "").strip().casefold()
    return f"{normalized_summary}|{normalized_start}"


def normalize_calendar_event(*, calendar_id: str, event: dict) -> dict:
    start_ts = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
    end_ts = (event.get("end") or {}).get("dateTime") or (event.get("end") or {}).get("date")
    summary = event.get("summary")
    return {
        "event_id": event["id"],
        "calendar_id": calendar_id,
        "summary": summary,
        "status": event.get("status"),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "location": event.get("location"),
        "html_link": event.get("htmlLink"),
        "dedup_key": build_dedup_key(summary, start_ts),
    }


def _default_runner(args: list[str]) -> str:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout


def build_fake_calendar_runner() -> Callable[[list[str]], str]:
    def runner(args: list[str]) -> str:
        if args[:4] == ["gws", "calendar", "events", "list"]:
            return json.dumps(
                {
                    "items": [
                        {
                            "id": "evt-1",
                            "summary": "Advanced Computer Networking",
                            "status": "confirmed",
                            "start": {"dateTime": "2026-04-21T13:00:00+09:00", "timeZone": "Asia/Seoul"},
                            "end": {"dateTime": "2026-04-21T14:30:00+09:00", "timeZone": "Asia/Seoul"},
                        },
                        {
                            "id": "evt-2",
                            "summary": "[TA] SW 기초 및 코딩",
                            "status": "confirmed",
                            "start": {"dateTime": "2026-04-22T13:00:00+09:00", "timeZone": "Asia/Seoul"},
                            "end": {"dateTime": "2026-04-22T16:00:00+09:00", "timeZone": "Asia/Seoul"},
                        },
                    ]
                },
                ensure_ascii=False,
            )
        raise AssertionError(f"unexpected fake command: {args}")

    return runner


def _load_checkpoints(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_checkpoints(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_file(snapshot_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return snapshot_dir / f"calendar-{timestamp}.jsonl"


def _append_calendar_rows(database_path: Path, rows: list[dict]) -> None:
    with sqlite3.connect(database_path) as conn:
        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO calendar_events (
                    event_id, calendar_id, summary, status, start_ts, end_ts,
                    location, html_link, dedup_key, raw_json_path, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["event_id"],
                    row["calendar_id"],
                    row.get("summary"),
                    row.get("status"),
                    row.get("start_ts"),
                    row.get("end_ts"),
                    row.get("location"),
                    row.get("html_link"),
                    row.get("dedup_key"),
                    None,
                    datetime.now(UTC).isoformat(),
                ),
            )
        conn.commit()


def collect_calendar_snapshots(config: PipelineConfig, *, runner: Callable[[list[str]], str] | None = None) -> dict:
    runner = runner or _default_runner
    bootstrap_workspace(config)
    params = json.dumps(
        {
            "calendarId": config.calendar_id,
            "maxResults": config.calendar_max_results,
            "singleEvents": True,
            "orderBy": "startTime",
            "timeMin": config.calendar_time_min,
            "timeMax": config.calendar_time_max,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    raw = runner(["gws", "calendar", "events", "list", "--params", params, "--format", "json"])
    payload = json.loads(raw)
    items = payload.get("items", [])
    rows = [normalize_calendar_event(calendar_id=config.calendar_id, event=item) for item in items]

    snapshot_path = _snapshot_file(config.calendar_snapshot_dir)
    snapshot_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    _append_calendar_rows(config.database_path, rows)

    checkpoints = _load_checkpoints(config.checkpoints_path)
    checkpoints.setdefault("calendar", {})
    checkpoints["calendar"][config.calendar_id] = {
        "last_snapshot_file": snapshot_path.name,
        "event_count": len(rows),
        "collected_at": datetime.now(UTC).isoformat(),
        "time_min": config.calendar_time_min,
        "time_max": config.calendar_time_max,
    }
    _save_checkpoints(config.checkpoints_path, checkpoints)

    return {
        "snapshot_file": snapshot_path,
        "calendar_id": config.calendar_id,
        "event_count": len(rows),
    }
