import sqlite3
from pathlib import Path

import pytest

from jinwang_jarvis.zeus_os import schema, store


def _in_memory_store():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in store.DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


class TestSchemaMigrations:
    def test_initial_migration_creates_all_tables(self):
        conn = _in_memory_store()
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {row[0] for row in cur.fetchall()}
        expected = {
            "schema_migrations",
            "runtime_metadata",
            "agent_cards",
            "worker_agents",
            "contexts",
            "boardroom_sessions",
            "boardroom_participants",
            "messages",
            "tasks",
            "agenda_items",
            "decisions",
            "approvals",
            "task_events",
            "work_orders",
            "bus_queue",
            "artifacts",
            "projection_offsets",
            "dashboard_messages",
        }
        assert expected <= names

    def test_schema_version_returns_positive(self):
        conn = _in_memory_store()
        version = schema.get_schema_version(conn)
        assert version >= 1

    def test_default_agents_seeded(self):
        conn = _in_memory_store()
        cur = conn.execute("SELECT agent_id FROM agent_cards")
        ids = {row[0] for row in cur.fetchall()}
        expected = {
            "chair", "pm", "researcher", "engineer", "critic",
            "scribe", "qa", "ops", "security_auditor", "cost_controller",
            "memory_curator", "painter", "system",
        }
        assert expected <= ids

    def test_foreign_keys_enabled(self):
        conn = _in_memory_store()
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

    def test_wal_mode(self):
        conn = _in_memory_store()
        row = conn.execute("PRAGMA journal_mode").fetchone()
        mode = row[0].upper()
        assert mode == "WAL" or mode == "MEMORY"

    def test_apply_migrations_is_idempotent(self):
        conn = _in_memory_store()
        v1 = schema.get_schema_version(conn)
        v2 = schema.apply_migrations(conn)
        assert v1 == v2


class TestStoreHelpers:
    def test_now_utc_is_iso8601(self):
        ts = store.now_utc()
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_json_dumps_roundtrips(self):
        obj = {"a": 1, "b": [2, 3]}
        text = store.json_dumps(obj)
        assert store.json_loads(text) == obj

    def test_allocate_sequence_increments(self):
        conn = _in_memory_store()
        seq1 = store.allocate_sequence(conn, "tsk_test")
        conn.execute("INSERT INTO task_events (event_id, task_id, event_type, actor_type, sequence, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     ("evt_1", "tsk_test", "a", "user", seq1, "{}", store.now_utc()))
        seq2 = store.allocate_sequence(conn, "tsk_test")
        assert seq2 == seq1 + 1

    def test_transaction_commits_on_success(self):
        conn = _in_memory_store()
        with store.transaction(conn):
            conn.execute("INSERT INTO runtime_metadata (key, value_json, updated_at) VALUES (?, ?, ?)", ("k", "{}", store.now_utc()))
        cur = conn.execute("SELECT 1 FROM runtime_metadata WHERE key = ?", ("k",))
        assert cur.fetchone() is not None

    def test_transaction_rolls_back_on_error(self):
        conn = _in_memory_store()
        try:
            with store.transaction(conn):
                conn.execute("INSERT INTO runtime_metadata (key, value_json, updated_at) VALUES (?, ?, ?)", ("k2", "{}", store.now_utc()))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        cur = conn.execute("SELECT 1 FROM runtime_metadata WHERE key = ?", ("k2",))
        assert cur.fetchone() is None
