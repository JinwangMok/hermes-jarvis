"""Export tasks/events/artifacts to JSONL and other formats."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import safety, store


def export_task_jsonl(
    conn: sqlite3.Connection,
    task_id: str,
    output_path: Path,
) -> dict[str, Any]:
    events = []
    cur = conn.execute(
        """
        SELECT event_id, event_type, actor_type, actor_id, sequence, payload_json, created_at
        FROM task_events WHERE task_id = ? ORDER BY sequence ASC
        """,
        (task_id,),
    )
    for row in cur.fetchall():
        events.append({
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "actor_type": row["actor_type"],
            "actor_id": row["actor_id"],
            "sequence": row["sequence"],
            "payload": safety.redact_value(store.json_loads(row["payload_json"])),
            "created_at": row["created_at"],
        })

    cur = conn.execute(
        """
        SELECT artifact_id, name, kind, media_type, uri, sha256, size_bytes, created_at
        FROM artifacts WHERE task_id = ?
        """,
        (task_id,),
    )
    artifacts = []
    for row in cur.fetchall():
        artifacts.append({
            "artifact_id": row["artifact_id"],
            "name": row["name"],
            "kind": row["kind"],
            "media_type": row["media_type"],
            "uri": row["uri"],
            "sha256": row["sha256"],
            "size_bytes": row["size_bytes"],
            "created_at": row["created_at"],
        })

    cur = conn.execute(
        """
        SELECT task_id, title, user_goal, state, priority, progress_percent, budget_json, result_summary, created_at, updated_at, completed_at
        FROM tasks WHERE task_id = ?
        """,
        (task_id,),
    )
    row = cur.fetchone()
    task = {
        "task_id": row["task_id"],
        "title": row["title"],
        "user_goal": safety.redact_value(row["user_goal"]),
        "state": row["state"],
        "priority": row["priority"],
        "progress_percent": row["progress_percent"],
        "budget": safety.redact_value(store.json_loads(row["budget_json"])),
        "result_summary": safety.redact_value(row["result_summary"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    } if row else {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "task", "data": task}, ensure_ascii=False) + "\n")
        for evt in events:
            f.write(json.dumps({"type": "event", "data": evt}, ensure_ascii=False) + "\n")
        for art in artifacts:
            f.write(json.dumps({"type": "artifact", "data": art}, ensure_ascii=False) + "\n")

    return {
        "output_path": str(output_path),
        "event_count": len(events),
        "artifact_count": len(artifacts),
    }
