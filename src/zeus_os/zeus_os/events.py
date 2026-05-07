"""Event sourcing for tasks with atomic sequence allocation."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import ids, store


def append_event(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    event_type: str,
    actor_type: str,
    actor_id: str | None = None,
    context_id: str | None = None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    schema_version: int = 1,
) -> dict[str, Any]:
    sequence = store.allocate_sequence(conn, task_id)
    event_id = ids.generate_id("event")
    now = store.now_utc()
    payload_json = store.json_dumps(payload or {})

    conn.execute(
        """
        INSERT INTO task_events (
            event_id, task_id, context_id, event_type, actor_type, actor_id,
            sequence, correlation_id, causation_id, idempotency_key,
            schema_version, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id, task_id, context_id, event_type, actor_type, actor_id,
            sequence, correlation_id, causation_id, idempotency_key,
            schema_version, payload_json, now,
        ),
    )
    return {
        "event_id": event_id,
        "task_id": task_id,
        "sequence": sequence,
        "created_at": now,
    }


def get_events_for_task(
    conn: sqlite3.Connection,
    task_id: str,
    after_sequence: int = 0,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT event_id, task_id, context_id, event_type, actor_type, actor_id,
               sequence, correlation_id, causation_id, idempotency_key,
               schema_version, payload_json, created_at
        FROM task_events
        WHERE task_id = ? AND sequence > ?
        ORDER BY sequence ASC
        LIMIT ?
        """,
        (task_id, after_sequence, limit),
    )
    rows = []
    for row in cur.fetchall():
        rows.append({
            "event_id": row["event_id"],
            "task_id": row["task_id"],
            "context_id": row["context_id"],
            "event_type": row["event_type"],
            "actor_type": row["actor_type"],
            "actor_id": row["actor_id"],
            "sequence": row["sequence"],
            "correlation_id": row["correlation_id"],
            "causation_id": row["causation_id"],
            "idempotency_key": row["idempotency_key"],
            "schema_version": row["schema_version"],
            "payload": store.json_loads(row["payload_json"]),
            "created_at": row["created_at"],
        })
    return rows


def get_latest_event_sequence(conn: sqlite3.Connection, task_id: str) -> int:
    cur = conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) FROM task_events WHERE task_id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    return row[0] if row else 0


def get_events_for_projection(
    conn: sqlite3.Connection,
    projection_name: str,
    task_id: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    if task_id:
        cur = conn.execute(
            """
            SELECT e.* FROM task_events e
            JOIN projection_offsets po
              ON po.projection_name = ? AND po.task_id = ?
            WHERE e.task_id = ? AND e.sequence > po.last_event_sequence
            ORDER BY e.sequence ASC
            LIMIT ?
            """,
            (projection_name, task_id, task_id, limit),
        )
    else:
        cur = conn.execute(
            """
            SELECT e.* FROM task_events e
            JOIN projection_offsets po
              ON po.projection_name = ? AND (po.task_id = e.task_id OR po.task_id IS NULL)
            WHERE e.sequence > po.last_event_sequence
            ORDER BY e.sequence ASC
            LIMIT ?
            """,
            (projection_name, limit),
        )
    rows = []
    for row in cur.fetchall():
        rows.append(dict(row))
    return rows


def update_projection_offset(
    conn: sqlite3.Connection,
    projection_name: str,
    task_id: str | None,
    last_event_sequence: int,
    status: str = "active",
    error_summary: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO projection_offsets (projection_name, task_id, last_event_sequence, status, error_summary, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(projection_name, task_id) DO UPDATE SET
            last_event_sequence=excluded.last_event_sequence,
            status=excluded.status,
            error_summary=excluded.error_summary,
            updated_at=excluded.updated_at
        """,
        (projection_name, task_id, last_event_sequence, status, error_summary, store.now_utc()),
    )
