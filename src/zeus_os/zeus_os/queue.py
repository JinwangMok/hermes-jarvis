"""Atomic queue and work order lifecycle."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import ids, store


QUEUE_STATES = {"ready", "leased", "acked", "dead", "canceled"}
WORK_ORDER_STATES = {"ready", "running", "completed", "retryable", "failed", "canceled", "approval_required"}


def enqueue(
    conn: sqlite3.Connection,
    topic: str,
    payload: dict[str, Any],
    *,
    key: str | None = None,
    max_attempts: int = 3,
    idempotency_key: str | None = None,
    available_at: str | None = None,
) -> str:
    queue_id = ids.generate_id("queue")
    now = store.now_utc()
    conn.execute(
        """
        INSERT INTO bus_queue (queue_id, topic, key, payload_json, state, max_attempts, available_at, idempotency_key, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'ready', ?, ?, ?, ?, ?)
        """,
        (queue_id, topic, key, store.json_dumps(payload), max_attempts, available_at or now, idempotency_key, now, now),
    )
    return queue_id


def claim_next(
    conn: sqlite3.Connection,
    topic: str,
    lease_owner: str,
    lease_seconds: int = 60,
) -> dict[str, Any] | None:
    now = store.now_utc()
    with store.transaction(conn):
        cur = conn.execute(
            """
            SELECT queue_id, payload_json, attempt_count, max_attempts
            FROM bus_queue
            WHERE topic = ? AND state = 'ready' AND (available_at IS NULL OR available_at <= ?)
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (topic, now),
        )
        row = cur.fetchone()
        if not row:
            return None

        queue_id, payload_json, attempt_count, max_attempts = row
        lease_expires = _add_seconds(now, lease_seconds)
        new_attempt = attempt_count + 1

        payload = store.json_loads(payload_json)
        work_order_id = payload.get("work_order_id")
        if work_order_id:
            _claim_work_order(conn, work_order_id, lease_owner, lease_expires, now)

        cur = conn.execute(
            """
            UPDATE bus_queue
            SET state = 'leased', lease_owner = ?, lease_expires_at = ?, attempt_count = ?, updated_at = ?
            WHERE queue_id = ? AND state = 'ready'
            """,
            (lease_owner, lease_expires, new_attempt, now, queue_id),
        )
        if cur.rowcount != 1:
            raise RuntimeError(f"Queue lease failed: {queue_id}")

        return {
            "queue_id": queue_id,
            "topic": topic,
            "payload": payload,
            "attempt_count": new_attempt,
            "max_attempts": max_attempts,
            "lease_expires_at": lease_expires,
        }


def ack(
    conn: sqlite3.Connection,
    queue_id: str,
    lease_owner: str,
    *,
    work_order_result: dict[str, Any] | None = None,
) -> None:
    now = store.now_utc()
    with store.transaction(conn):
        _verify_lease(conn, queue_id, lease_owner)
        conn.execute(
            "UPDATE bus_queue SET state = 'acked', lease_owner = NULL, lease_expires_at = NULL, updated_at = ? WHERE queue_id = ?",
            (now, queue_id),
        )
        payload = _get_payload(conn, queue_id)
        work_order_id = payload.get("work_order_id")
        if work_order_id:
            _finish_work_order(
                conn,
                work_order_id,
                lease_owner,
                "completed",
                now,
                result_summary=store.json_dumps(work_order_result) if work_order_result else None,
            )


def nack(
    conn: sqlite3.Connection,
    queue_id: str,
    lease_owner: str,
    error_summary: str = "",
    backoff_seconds: int = 5,
) -> None:
    now = store.now_utc()
    with store.transaction(conn):
        _verify_lease(conn, queue_id, lease_owner)
        cur = conn.execute(
            "SELECT attempt_count, max_attempts FROM bus_queue WHERE queue_id = ?",
            (queue_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Queue item not found: {queue_id}")
        attempt_count, max_attempts = row

        if attempt_count >= max_attempts:
            conn.execute(
                "UPDATE bus_queue SET state = 'dead', lease_owner = NULL, lease_expires_at = NULL, updated_at = ? WHERE queue_id = ?",
                (now, queue_id),
            )
            payload = _get_payload(conn, queue_id)
            work_order_id = payload.get("work_order_id")
            if work_order_id:
                _finish_work_order(conn, work_order_id, lease_owner, "failed", now, error_summary=error_summary)
        else:
            next_available = _add_seconds(now, backoff_seconds)
            conn.execute(
                """
                UPDATE bus_queue
                SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL, available_at = ?, updated_at = ?
                WHERE queue_id = ?
                """,
                (next_available, now, queue_id),
            )
            payload = _get_payload(conn, queue_id)
            work_order_id = payload.get("work_order_id")
            if work_order_id:
                _reset_work_order(conn, work_order_id, lease_owner, "retryable", now)


def cancel(
    conn: sqlite3.Connection,
    queue_id: str,
    lease_owner: str,
) -> None:
    now = store.now_utc()
    with store.transaction(conn):
        _verify_lease(conn, queue_id, lease_owner)
        conn.execute(
            "UPDATE bus_queue SET state = 'canceled', lease_owner = NULL, lease_expires_at = NULL, updated_at = ? WHERE queue_id = ?",
            (now, queue_id),
        )
        payload = _get_payload(conn, queue_id)
        work_order_id = payload.get("work_order_id")
        if work_order_id:
            _finish_work_order(conn, work_order_id, lease_owner, "canceled", now)


def renew(
    conn: sqlite3.Connection,
    queue_id: str,
    lease_owner: str,
    lease_seconds: int = 60,
) -> None:
    now = store.now_utc()
    lease_expires = _add_seconds(now, lease_seconds)
    with store.transaction(conn):
        _verify_lease(conn, queue_id, lease_owner)
        conn.execute(
            "UPDATE bus_queue SET lease_expires_at = ?, updated_at = ? WHERE queue_id = ?",
            (lease_expires, now, queue_id),
        )
        payload = _get_payload(conn, queue_id)
        work_order_id = payload.get("work_order_id")
        if work_order_id:
            cur = conn.execute(
                """
                UPDATE work_orders
                SET lease_expires_at = ?, updated_at = ?, revision = revision + 1
                WHERE work_order_id = ? AND state = 'running' AND lease_owner = ?
                """,
                (lease_expires, now, work_order_id, lease_owner),
            )
            if cur.rowcount != 1:
                raise PermissionError(f"Work order lease mismatch: {work_order_id}")


def recover_expired(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    now = store.now_utc()
    with store.transaction(conn):
        cur = conn.execute(
            """
            SELECT queue_id, topic, payload_json, attempt_count, max_attempts, lease_owner
            FROM bus_queue
            WHERE state = 'leased' AND lease_expires_at < ?
            """,
            (now,),
        )
        expired = []
        for row in cur.fetchall():
            queue_id, topic, payload_json, attempt_count, max_attempts, lease_owner = row
            payload = store.json_loads(payload_json)
            work_order_id = payload.get("work_order_id")
            if attempt_count >= max_attempts:
                conn.execute(
                    "UPDATE bus_queue SET state = 'dead', lease_owner = NULL, lease_expires_at = NULL, updated_at = ? WHERE queue_id = ?",
                    (now, queue_id),
                )
                if work_order_id:
                    _finish_work_order(conn, work_order_id, lease_owner, "failed", now, error_summary="lease expired")
            else:
                conn.execute(
                    """
                    UPDATE bus_queue
                    SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                    WHERE queue_id = ?
                    """,
                    (now, queue_id),
                )
                if work_order_id:
                    _reset_work_order(conn, work_order_id, lease_owner, "retryable", now)
            expired.append({
                "queue_id": queue_id,
                "topic": topic,
                "payload": payload,
                "attempt_count": attempt_count,
                "max_attempts": max_attempts,
                "previous_owner": lease_owner,
            })
        return expired


def create_work_order(
    conn: sqlite3.Connection,
    task_id: str,
    worker_kind: str,
    instruction_summary: str,
    *,
    parent_work_order_id: str | None = None,
    capability_required: str | None = None,
    instruction_path: str | None = None,
    max_attempts: int = 3,
    metadata: dict[str, Any] | None = None,
) -> str:
    work_order_id = ids.generate_id("work_order")
    now = store.now_utc()
    conn.execute(
        """
        INSERT INTO work_orders (
            work_order_id, task_id, parent_work_order_id, worker_kind, capability_required,
            instruction_summary, instruction_path, state, max_attempts, metadata_json, revision, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, 1, ?, ?)
        """,
        (work_order_id, task_id, parent_work_order_id, worker_kind, capability_required,
         instruction_summary, instruction_path, max_attempts, store.json_dumps(metadata or {}), now, now),
    )
    return work_order_id


def list_queue_state(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.execute("SELECT state, COUNT(*) FROM bus_queue GROUP BY state")
    return {row[0]: row[1] for row in cur.fetchall()}


def list_dead_letters(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT queue_id, topic, payload_json, attempt_count, created_at
        FROM bus_queue WHERE state = 'dead'
        ORDER BY created_at DESC
        """
    )
    rows = []
    for row in cur.fetchall():
        rows.append({
            "queue_id": row["queue_id"],
            "topic": row["topic"],
            "payload": store.json_loads(row["payload_json"]),
            "attempt_count": row["attempt_count"],
            "created_at": row["created_at"],
        })
    return rows


def _claim_work_order(conn: sqlite3.Connection, work_order_id: str, lease_owner: str, lease_expires: str, now: str) -> None:
    cur = conn.execute(
        """
        UPDATE work_orders
        SET state = 'running', lease_owner = ?, lease_expires_at = ?, attempt_count = attempt_count + 1, updated_at = ?, revision = revision + 1
        WHERE work_order_id = ? AND state IN ('ready', 'retryable') AND (lease_owner IS NULL OR lease_owner = ?)
        """,
        (lease_owner, lease_expires, now, work_order_id, lease_owner),
    )
    if cur.rowcount != 1:
        raise ValueError(f"Work order is not claimable: {work_order_id}")


def _finish_work_order(
    conn: sqlite3.Connection,
    work_order_id: str,
    lease_owner: str | None,
    state: str,
    now: str,
    *,
    result_summary: str | None = None,
    error_summary: str | None = None,
) -> None:
    cur = conn.execute(
        """
        UPDATE work_orders
        SET state = ?, lease_owner = NULL, lease_expires_at = NULL, result_summary = COALESCE(?, result_summary),
            error_summary = COALESCE(?, error_summary), updated_at = ?, completed_at = ?, revision = revision + 1
        WHERE work_order_id = ? AND state = 'running' AND (lease_owner = ? OR ? IS NULL)
        """,
        (state, result_summary, error_summary, now, now, work_order_id, lease_owner, lease_owner),
    )
    if cur.rowcount != 1:
        raise PermissionError(f"Work order lease mismatch: {work_order_id}")


def _reset_work_order(conn: sqlite3.Connection, work_order_id: str, lease_owner: str, state: str, now: str) -> None:
    cur = conn.execute(
        """
        UPDATE work_orders
        SET state = ?, lease_owner = NULL, lease_expires_at = NULL, updated_at = ?, revision = revision + 1
        WHERE work_order_id = ? AND state = 'running' AND lease_owner = ?
        """,
        (state, now, work_order_id, lease_owner),
    )
    if cur.rowcount != 1:
        raise PermissionError(f"Work order lease mismatch: {work_order_id}")


def _verify_lease(conn: sqlite3.Connection, queue_id: str, lease_owner: str) -> None:
    cur = conn.execute(
        "SELECT lease_owner FROM bus_queue WHERE queue_id = ?",
        (queue_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Queue item not found: {queue_id}")
    if row[0] != lease_owner:
        raise PermissionError(f"Lease mismatch: expected {lease_owner}, got {row[0]}")


def _get_payload(conn: sqlite3.Connection, queue_id: str) -> dict[str, Any]:
    cur = conn.execute(
        "SELECT payload_json FROM bus_queue WHERE queue_id = ?",
        (queue_id,),
    )
    row = cur.fetchone()
    if not row:
        return {}
    return store.json_loads(row[0])


def _add_seconds(iso_ts: str, seconds: int) -> str:
    from datetime import datetime, timezone, timedelta
    dt = datetime.fromisoformat(iso_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(seconds=seconds)).isoformat()
