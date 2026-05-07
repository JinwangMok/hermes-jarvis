"""Bounded boardroom session management."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import events, ids, store


def create_session(
    conn: sqlite3.Connection,
    title: str,
    *,
    context_id: str | None = None,
    task_id: str | None = None,
    max_rounds: int = 5,
    final_arbiter_agent_id: str | None = None,
    budget: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    session_id = ids.generate_id("session")
    now = store.now_utc()
    conn.execute(
        """
        INSERT INTO boardroom_sessions (
            session_id, context_id, task_id, title, status, max_rounds, current_round,
            final_arbiter_agent_id, budget_json, metadata_json, revision, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'open', ?, 0, ?, ?, ?, 1, ?, ?)
        """,
        (session_id, context_id, task_id, title, max_rounds, final_arbiter_agent_id,
         store.json_dumps(budget or {}), store.json_dumps(metadata or {}), now, now),
    )
    return session_id


def add_participant(
    conn: sqlite3.Connection,
    session_id: str,
    agent_id: str,
    *,
    role: str = "participant",
    turn_budget: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = store.now_utc()
    conn.execute(
        """
        INSERT INTO boardroom_participants (session_id, agent_id, role, status, turn_budget_json, metadata_json, joined_at, updated_at)
        VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
        ON CONFLICT(session_id, agent_id) DO UPDATE SET
            role=excluded.role,
            status=excluded.status,
            turn_budget_json=excluded.turn_budget_json,
            metadata_json=excluded.metadata_json,
            updated_at=excluded.updated_at
        """,
        (session_id, agent_id, role, store.json_dumps(turn_budget or {}), store.json_dumps(metadata or {}), now, now),
    )


def advance_round(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    now = store.now_utc()
    with store.transaction(conn):
        cur = conn.execute(
            "SELECT max_rounds, current_round, status FROM boardroom_sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Session not found: {session_id}")
        max_rounds, current_round, status = row
        if status != "open":
            raise ValueError(f"Session not open: {status}")
        if current_round >= max_rounds:
            conn.execute(
                """
                UPDATE boardroom_sessions
                SET status = 'closed', completed_at = ?, updated_at = ?, revision = revision + 1
                WHERE session_id = ?
                """,
                (now, now, session_id),
            )
            return {"session_id": session_id, "status": "closed", "reason": "max_rounds_reached"}

        new_round = current_round + 1
        conn.execute(
            """
            UPDATE boardroom_sessions
            SET current_round = ?, updated_at = ?, revision = revision + 1
            WHERE session_id = ?
            """,
            (new_round, now, session_id),
        )
        # Append event
        events.append_event(
            conn,
            task_id=session_id,
            event_type="round.started",
            actor_type="system",
            payload={"round": new_round, "max_rounds": max_rounds},
        )
        return {"session_id": session_id, "current_round": new_round, "max_rounds": max_rounds}


def close_session(
    conn: sqlite3.Connection,
    session_id: str,
    decided_by: str,
) -> None:
    now = store.now_utc()
    with store.transaction(conn):
        conn.execute(
            """
            UPDATE boardroom_sessions
            SET status = 'closed', completed_at = ?, updated_at = ?, revision = revision + 1
            WHERE session_id = ?
            """,
            (now, now, session_id),
        )
        events.append_event(
            conn,
            task_id=session_id,
            event_type="round.closed",
            actor_type="agent",
            actor_id=decided_by,
            payload={"reason": "arbiter_closed"},
        )


def get_session_status(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    cur = conn.execute("SELECT * FROM boardroom_sessions WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    if not row:
        return None
    session = dict(row)
    cur = conn.execute(
        """
        SELECT agent_id, role, status, turn_budget_json
        FROM boardroom_participants WHERE session_id = ?
        """,
        (session_id,),
    )
    session["participants"] = [dict(r) for r in cur.fetchall()]
    return session


def propose_agenda_item(
    conn: sqlite3.Connection,
    session_id: str,
    title: str,
    *,
    task_id: str | None = None,
    convergence_condition: str = "",
    final_arbiter_agent_id: str | None = None,
    turn_budget: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    agenda_item_id = ids.generate_id("agenda")
    now = store.now_utc()
    conn.execute(
        """
        INSERT INTO agenda_items (
            agenda_item_id, session_id, task_id, title, state, turn_budget_json,
            convergence_condition, final_arbiter_agent_id, metadata_json, revision, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, 1, ?, ?)
        """,
        (agenda_item_id, session_id, task_id, title, store.json_dumps(turn_budget or {}),
         convergence_condition, final_arbiter_agent_id, store.json_dumps(metadata or {}), now, now),
    )
    return agenda_item_id
