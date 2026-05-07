import json
import sqlite3
from pathlib import Path

from zeus_os.cli import main
from zeus_os.zeus_os import queue, schema, store, worker


def _in_memory_store():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in store.DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


def _create_task(conn, task_id="tsk_1"):
    now = store.now_utc()
    conn.execute(
        "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
        (task_id, "Deterministic worker task", now, now),
    )
    return task_id


def _last_json(capsys):
    out = capsys.readouterr().out.strip()
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return json.loads(lines[-1])


def test_deterministic_worker_returns_no_work_when_queue_empty(tmp_path: Path):
    conn = _in_memory_store()

    result = worker.run_deterministic_once(conn, tmp_path)

    assert result == {"ok": True, "action": "no_work"}


def test_deterministic_worker_completes_work_order_with_event_and_artifact(tmp_path: Path):
    conn = _in_memory_store()
    task_id = _create_task(conn)
    work_order_id = queue.create_work_order(conn, task_id, "deterministic", "write deterministic evidence")
    qid = queue.enqueue(conn, "worker.deterministic", {"task_id": task_id, "work_order_id": work_order_id})

    result = worker.run_deterministic_once(conn, tmp_path)

    assert result["ok"] is True
    assert result["queue_id"] == qid
    assert result["work_order_id"] == work_order_id
    assert result["artifact_id"].startswith("art_")
    assert result["event_id"].startswith("evt_")

    queue_row = conn.execute("SELECT state FROM bus_queue WHERE queue_id = ?", (qid,)).fetchone()
    work_row = conn.execute("SELECT state, result_summary FROM work_orders WHERE work_order_id = ?", (work_order_id,)).fetchone()
    event_row = conn.execute("SELECT event_type, payload_json FROM task_events WHERE event_id = ?", (result["event_id"],)).fetchone()
    artifact_row = conn.execute("SELECT uri, sha256 FROM artifacts WHERE artifact_id = ?", (result["artifact_id"],)).fetchone()

    assert queue_row["state"] == "acked"
    assert work_row["state"] == "completed"
    assert json.loads(work_row["result_summary"])["artifact_id"] == result["artifact_id"]
    assert event_row["event_type"] == "worker.completed"
    assert json.loads(event_row["payload_json"])["artifact_id"] == result["artifact_id"]
    artifact_path = tmp_path / artifact_row["uri"]
    assert artifact_path.exists()
    assert artifact_row["sha256"]


def test_cli_worker_run_uses_deterministic_fixture(tmp_path: Path, capsys):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    main(["zeus", "init", "--workspace", str(workspace)])
    main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Queued task"])
    task_id = _last_json(capsys)["task_id"]

    config = store.StoreConfig.from_workspace(str(workspace))
    conn = store.init_store(config)
    work_order_id = queue.create_work_order(conn, task_id, "deterministic", "cli fixture")
    queue.enqueue(conn, "worker.deterministic", {"task_id": task_id, "work_order_id": work_order_id})
    conn.commit()
    conn.close()

    ret = main(["zeus", "worker", "run", "--workspace", str(workspace), "--once"])
    result = _last_json(capsys)

    assert ret == 0
    assert result["ok"] is True
    assert result["work_order_id"] == work_order_id
    assert (workspace / "data" / "zeus" / "tasks" / task_id / work_order_id / "deterministic-worker-result.json").exists()
