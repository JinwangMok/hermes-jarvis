import sqlite3

import pytest

from zeus_os.zeus_os import events, schema, store


def _in_memory_store():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in store.DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


class TestEventAppend:
    def test_append_event_allocates_sequence(self):
        conn = _in_memory_store()
        result = events.append_event(
            conn, task_id="tsk_1", event_type="task.proposed", actor_type="user"
        )
        assert result["sequence"] == 1
        assert result["event_id"].startswith("evt_")

    def test_append_multiple_events_increments_sequence(self):
        conn = _in_memory_store()
        r1 = events.append_event(conn, task_id="tsk_1", event_type="a", actor_type="user")
        r2 = events.append_event(conn, task_id="tsk_1", event_type="b", actor_type="system")
        assert r2["sequence"] == r1["sequence"] + 1

    def test_events_for_task_returns_ordered(self):
        conn = _in_memory_store()
        events.append_event(conn, task_id="tsk_1", event_type="a", actor_type="user")
        events.append_event(conn, task_id="tsk_1", event_type="b", actor_type="system")
        evts = events.get_events_for_task(conn, "tsk_1")
        assert len(evts) == 2
        assert evts[0]["sequence"] < evts[1]["sequence"]

    def test_events_after_sequence_filter(self):
        conn = _in_memory_store()
        events.append_event(conn, task_id="tsk_1", event_type="a", actor_type="user")
        events.append_event(conn, task_id="tsk_1", event_type="b", actor_type="system")
        evts = events.get_events_for_task(conn, "tsk_1", after_sequence=1)
        assert len(evts) == 1
        assert evts[0]["event_type"] == "b"

    def test_payload_roundtrips(self):
        conn = _in_memory_store()
        payload = {"key": "value", "nested": {"x": 1}}
        events.append_event(conn, task_id="tsk_1", event_type="x", actor_type="user", payload=payload)
        evts = events.get_events_for_task(conn, "tsk_1")
        assert evts[0]["payload"] == payload

    def test_unique_task_sequence_constraint(self):
        conn = _in_memory_store()
        events.append_event(conn, task_id="tsk_1", event_type="a", actor_type="user")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO task_events (event_id, task_id, event_type, actor_type, sequence, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("evt_dup", "tsk_1", "b", "system", 1, "{}", store.now_utc()),
            )

    def test_idempotency_key_uniqueness(self):
        conn = _in_memory_store()
        key = "unique-key-1"
        events.append_event(conn, task_id="tsk_1", event_type="a", actor_type="user", idempotency_key=key)
        with pytest.raises(sqlite3.IntegrityError):
            events.append_event(conn, task_id="tsk_1", event_type="b", actor_type="user", idempotency_key=key)

    def test_latest_event_sequence(self):
        conn = _in_memory_store()
        assert events.get_latest_event_sequence(conn, "tsk_1") == 0
        events.append_event(conn, task_id="tsk_1", event_type="a", actor_type="user")
        assert events.get_latest_event_sequence(conn, "tsk_1") == 1

    def test_projection_offset_update(self):
        conn = _in_memory_store()
        events.update_projection_offset(conn, "discord", "tsk_1", 5)
        cur = conn.execute("SELECT last_event_sequence FROM projection_offsets WHERE projection_name = ? AND task_id = ?", ("discord", "tsk_1"))
        assert cur.fetchone()[0] == 5

    def test_projection_offset_upsert(self):
        conn = _in_memory_store()
        events.update_projection_offset(conn, "discord", "tsk_1", 3)
        events.update_projection_offset(conn, "discord", "tsk_1", 7)
        cur = conn.execute("SELECT last_event_sequence FROM projection_offsets WHERE projection_name = ? AND task_id = ?", ("discord", "tsk_1"))
        assert cur.fetchone()[0] == 7
