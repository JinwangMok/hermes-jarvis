"""A2A projection mapping: internal state to A2A-compatible structures."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import safety, store


_TASK_STATE_MAP = {
    "submitted": "TASK_STATE_SUBMITTED",
    "working": "TASK_STATE_WORKING",
    "completed": "TASK_STATE_COMPLETED",
    "failed": "TASK_STATE_FAILED",
    "canceled": "TASK_STATE_CANCELED",
    "input_required": "TASK_STATE_INPUT_REQUIRED",
    "rejected": "TASK_STATE_REJECTED",
    "auth_required": "TASK_STATE_AUTH_REQUIRED",
}


def to_a2a_task_status(internal_state: str) -> str:
    return _TASK_STATE_MAP.get(internal_state, "TASK_STATE_UNKNOWN")


def agent_card_to_a2a(conn: sqlite3.Connection, agent_id: str) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM agent_cards WHERE agent_id = ?", (agent_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "agent_id": row["agent_id"],
        "name": row["name"],
        "persona_type": row["persona_type"],
        "description": row["description"],
        "version": row["version"],
        "capabilities": store.json_loads(row["capabilities_json"]),
        "skills": store.json_loads(row["skills_json"]),
        "protocols": store.json_loads(row["protocols_json"]),
        "status": row["status"],
    }


def message_to_a2a(conn: sqlite3.Connection, message_id: str) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "message_id": row["message_id"],
        "role": row["role"],
        "sender_agent_id": row["sender_agent_id"],
        "parts": safety.redact_value(store.json_loads(row["parts_json"])),
        "summary": safety.redact_value(row["summary"]),
        "visibility": row["visibility"],
        "created_at": row["created_at"],
    }


def task_to_a2a(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "task_id": row["task_id"],
        "title": row["title"],
        "user_goal": safety.redact_value(row["user_goal"]),
        "state": to_a2a_task_status(row["state"]),
        "priority": row["priority"],
        "progress_percent": row["progress_percent"],
        "budget": safety.redact_value(store.json_loads(row["budget_json"])),
        "result_summary": safety.redact_value(row["result_summary"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


def artifact_to_a2a(conn: sqlite3.Connection, artifact_id: str) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "artifact_id": row["artifact_id"],
        "name": row["name"],
        "kind": row["kind"],
        "media_type": row["media_type"],
        "uri": row["uri"],
        "visibility": row["visibility"],
        "sha256": row["sha256"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
    }
