import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from jinwang_jarvis.zeus_os import queue, schema, store


def _in_memory_store():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in store.DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


class TestQueueLifecycle:
    def test_enqueue_creates_ready_item(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"})
        cur = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,))
        assert cur.fetchone()[0] == "ready"

    def test_claim_next_leases_item(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"})
        claimed = queue.claim_next(conn, "worker.test", "worker-1", lease_seconds=60)
        assert claimed is not None
        assert claimed["queue_id"] == qid
        cur = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,))
        assert cur.fetchone()[0] == "leased"

    def test_claim_next_returns_none_when_empty(self):
        conn = _in_memory_store()
        claimed = queue.claim_next(conn, "worker.test", "worker-1")
        assert claimed is None

    def test_ack_completes_item(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"})
        claimed = queue.claim_next(conn, "worker.test", "worker-1")
        queue.ack(conn, qid, "worker-1")
        cur = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,))
        assert cur.fetchone()[0] == "acked"

    def test_ack_with_wrong_owner_fails(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"})
        queue.claim_next(conn, "worker.test", "worker-1")
        with pytest.raises(PermissionError):
            queue.ack(conn, qid, "worker-2")

    def test_nack_retries_then_dead(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"}, max_attempts=2)
        queue.claim_next(conn, "worker.test", "worker-1")
        queue.nack(conn, qid, "worker-1", error_summary="fail1", backoff_seconds=0)
        cur = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,))
        assert cur.fetchone()[0] == "ready"
        queue.claim_next(conn, "worker.test", "worker-1")
        queue.nack(conn, qid, "worker-1", error_summary="fail2", backoff_seconds=0)
        cur = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,))
        assert cur.fetchone()[0] == "dead"

    def test_cancel_cancels_item(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"})
        queue.claim_next(conn, "worker.test", "worker-1")
        queue.cancel(conn, qid, "worker-1")
        cur = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,))
        assert cur.fetchone()[0] == "canceled"

    def test_renew_extends_lease(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"})
        queue.claim_next(conn, "worker.test", "worker-1", lease_seconds=10)
        queue.renew(conn, qid, "worker-1", lease_seconds=300)
        cur = conn.execute("SELECT lease_expires_at FROM bus_queue WHERE queue_id = ?", (qid,))
        expires = cur.fetchone()[0]
        # Should be ~5 minutes from now
        dt = datetime.fromisoformat(expires)
        now = datetime.now(timezone.utc)
        assert dt > now + timedelta(seconds=200)

    def test_recover_expired_returns_to_ready(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {"task_id": "tsk_1"})
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        conn.execute("UPDATE bus_queue SET state = 'leased', lease_owner = 'w1', lease_expires_at = ? WHERE queue_id = ?", (past, qid))
        recovered = queue.recover_expired(conn)
        assert len(recovered) == 1
        assert recovered[0]["queue_id"] == qid
        cur = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,))
        assert cur.fetchone()[0] == "ready"

    def test_idempotency_key_unique(self):
        conn = _in_memory_store()
        key = "idem-1"
        queue.enqueue(conn, "worker.test", {}, idempotency_key=key)
        with pytest.raises(sqlite3.IntegrityError):
            queue.enqueue(conn, "worker.test", {}, idempotency_key=key)

    def test_list_queue_state(self):
        conn = _in_memory_store()
        queue.enqueue(conn, "worker.test", {})
        queue.enqueue(conn, "worker.test", {})
        state = queue.list_queue_state(conn)
        assert state.get("ready", 0) == 2

    def test_list_dead_letters(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.test", {}, max_attempts=1)
        queue.claim_next(conn, "worker.test", "w1")
        queue.nack(conn, qid, "w1")
        dead = queue.list_dead_letters(conn)
        assert len(dead) == 1


class TestWorkOrderLifecycle:
    def test_create_work_order(self):
        conn = _in_memory_store()
        conn.execute(
            "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
            ("tsk_1", "Test", store.now_utc(), store.now_utc()),
        )
        woid = queue.create_work_order(conn, "tsk_1", "deterministic", "do something")
        assert woid.startswith("wo_")
        cur = conn.execute("SELECT state FROM work_orders WHERE work_order_id = ?", (woid,))
        assert cur.fetchone()[0] == "ready"

    def test_claim_next_leases_work_order(self):
        conn = _in_memory_store()
        conn.execute(
            "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
            ("tsk_1", "Test", store.now_utc(), store.now_utc()),
        )
        woid = queue.create_work_order(conn, "tsk_1", "deterministic", "do something")
        qid = queue.enqueue(conn, "worker.deterministic", {"work_order_id": woid, "task_id": "tsk_1"})
        claimed = queue.claim_next(conn, "worker.deterministic", "w1")
        assert claimed["payload"]["work_order_id"] == woid
        cur = conn.execute("SELECT state FROM work_orders WHERE work_order_id = ?", (woid,))
        assert cur.fetchone()[0] == "running"

    def test_ack_completes_work_order(self):
        conn = _in_memory_store()
        conn.execute(
            "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
            ("tsk_1", "Test", store.now_utc(), store.now_utc()),
        )
        woid = queue.create_work_order(conn, "tsk_1", "deterministic", "do something")
        qid = queue.enqueue(conn, "worker.deterministic", {"work_order_id": woid, "task_id": "tsk_1"})
        queue.claim_next(conn, "worker.deterministic", "w1")
        queue.ack(conn, qid, "w1")
        cur = conn.execute("SELECT state FROM work_orders WHERE work_order_id = ?", (woid,))
        assert cur.fetchone()[0] == "completed"

    def test_claim_rolls_back_queue_when_work_order_missing(self):
        conn = _in_memory_store()
        qid = queue.enqueue(conn, "worker.deterministic", {"work_order_id": "wo_missing", "task_id": "tsk_1"})
        with pytest.raises(ValueError):
            queue.claim_next(conn, "worker.deterministic", "w1")
        cur = conn.execute("SELECT state, lease_owner FROM bus_queue WHERE queue_id = ?", (qid,))
        row = cur.fetchone()
        assert row[0] == "ready"
        assert row[1] is None

    def test_recover_expired_resets_work_order(self):
        conn = _in_memory_store()
        conn.execute(
            "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
            ("tsk_1", "Test", store.now_utc(), store.now_utc()),
        )
        woid = queue.create_work_order(conn, "tsk_1", "deterministic", "do something")
        qid = queue.enqueue(conn, "worker.deterministic", {"work_order_id": woid, "task_id": "tsk_1"})
        queue.claim_next(conn, "worker.deterministic", "w1")
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        conn.execute("UPDATE bus_queue SET lease_expires_at = ? WHERE queue_id = ?", (past, qid))
        queue.recover_expired(conn)
        cur = conn.execute("SELECT state, lease_owner FROM work_orders WHERE work_order_id = ?", (woid,))
        row = cur.fetchone()
        assert row[0] == "retryable"
        assert row[1] is None
