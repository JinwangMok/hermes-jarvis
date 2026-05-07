import sqlite3
from pathlib import Path

import pytest

from zeus_os.zeus_os import artifacts, schema, store


def _in_memory_store():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in store.DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


class TestArtifactWrite:
    def test_write_artifact_creates_file(self, tmp_path):
        record = artifacts.write_artifact(
            artifact_root=tmp_path,
            task_id="tsk_1",
            name="test.txt",
            kind="test",
            data=b"hello world",
        )
        assert record["artifact_id"].startswith("art_")
        assert record["sha256"] == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        file_path = tmp_path / "tsk_1" / "test.txt"
        assert file_path.read_bytes() == b"hello world"

    def test_register_artifact_in_db(self, tmp_path):
        conn = _in_memory_store()
        conn.execute(
            "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
            ("tsk_1", "Test", store.now_utc(), store.now_utc()),
        )
        record = artifacts.write_artifact(
            artifact_root=tmp_path,
            task_id="tsk_1",
            name="test.txt",
            kind="test",
            data=b"hello",
        )
        aid = artifacts.register_artifact(conn, record)
        cur = conn.execute("SELECT artifact_id, sha256 FROM artifacts WHERE artifact_id = ?", (aid,))
        row = cur.fetchone()
        assert row is not None
        assert row["sha256"] == record["sha256"]

    def test_read_artifact(self, tmp_path):
        record = artifacts.write_artifact(
            artifact_root=tmp_path,
            task_id="tsk_1",
            name="test.txt",
            kind="test",
            data=b"hello world",
        )
        data = artifacts.read_artifact(tmp_path, "tsk_1", record["uri"])
        assert data == b"hello world"

    def _store_with_task(self, tmp_path):
        conn = _in_memory_store()
        conn.execute(
            "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
            ("tsk_1", "Test", store.now_utc(), store.now_utc()),
        )
        return conn

    def test_reconcile_detects_missing_file(self, tmp_path):
        conn = self._store_with_task(tmp_path)
        record = artifacts.write_artifact(
            artifact_root=tmp_path,
            task_id="tsk_1",
            name="test.txt",
            kind="test",
            data=b"hello",
        )
        artifacts.register_artifact(conn, record)
        file_path = tmp_path / "tsk_1" / "test.txt"
        file_path.unlink()
        result = artifacts.reconcile_artifacts(conn, tmp_path)
        assert len(result["missing_files"]) == 1

    def test_reconcile_detects_hash_mismatch(self, tmp_path):
        conn = self._store_with_task(tmp_path)
        record = artifacts.write_artifact(
            artifact_root=tmp_path,
            task_id="tsk_1",
            name="test.txt",
            kind="test",
            data=b"hello",
        )
        artifacts.register_artifact(conn, record)
        file_path = tmp_path / "tsk_1" / "test.txt"
        file_path.write_text("corrupted")
        result = artifacts.reconcile_artifacts(conn, tmp_path)
        assert len(result["hash_mismatches"]) == 1

    def test_reconcile_detects_unregistered_file(self, tmp_path):
        conn = _in_memory_store()
        file_path = tmp_path / "tsk_1" / "orphan.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("orphan")
        result = artifacts.reconcile_artifacts(conn, tmp_path)
        assert len(result["unregistered_files"]) >= 1

    def test_guess_media_type(self):
        assert artifacts._guess_media_type("file.png") == "image/png"
        assert artifacts._guess_media_type("file.md") == "text/markdown"
        assert artifacts._guess_media_type("file.unknown") == "application/octet-stream"

    def test_write_artifact_with_work_order(self, tmp_path):
        record = artifacts.write_artifact(
            artifact_root=tmp_path,
            task_id="tsk_1",
            work_order_id="wo_1",
            name="result.txt",
            kind="result",
            data=b"result data",
        )
        assert (tmp_path / "tsk_1" / "wo_1" / "result.txt").exists()
    def test_write_artifact_rejects_unsafe_task_id(self, tmp_path):
        with pytest.raises(ValueError):
            artifacts.write_artifact(tmp_path, "../escape", "test.txt", "text", b"x")

    def test_write_artifact_rejects_unsafe_work_order_id(self, tmp_path):
        with pytest.raises(ValueError):
            artifacts.write_artifact(tmp_path, "tsk_1", "test.txt", "text", b"x", work_order_id="../wo")

    def test_write_artifact_rejects_nested_name(self, tmp_path):
        with pytest.raises(ValueError):
            artifacts.write_artifact(tmp_path, "tsk_1", "../test.txt", "text", b"x")

    def test_write_artifact_does_not_follow_predictable_tmp_symlink(self, tmp_path):
        outside = tmp_path / "outside.txt"
        outside.write_text("safe")
        target_dir = tmp_path / "tsk_1"
        target_dir.mkdir()
        (target_dir / "test.txt.tmp").symlink_to(outside)
        artifacts.write_artifact(tmp_path, "tsk_1", "test.txt", "text", b"PWN")
        assert outside.read_text() == "safe"
        assert (target_dir / "test.txt").read_bytes() == b"PWN"
