"""Zeus OS CLI subcommands."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from . import a2a, artifacts, boardroom, doctor, events, export, ids, painter, queue, safety, schema, store


def build_zeus_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jinwang-jarvis zeus")
    subparsers = parser.add_subparsers(dest="zeus_command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize Zeus OS schema and directories")
    init_parser.add_argument("--workspace", default=".", help="Workspace root directory")

    doctor_parser = subparsers.add_parser("doctor", help="Run Zeus OS health diagnostics")
    doctor_parser.add_argument("--workspace", default=".", help="Workspace root directory")

    task_parser = subparsers.add_parser("task", help="Task management")
    task_subparsers = task_parser.add_subparsers(dest="task_command", required=True)

    task_submit = task_subparsers.add_parser("submit", help="Submit a new task")
    task_submit.add_argument("--title", required=True, help="Task title")
    task_submit.add_argument("--goal", default="", help="User goal")
    task_submit.add_argument("--workspace", default=".", help="Workspace root directory")
    task_submit.add_argument("--priority", default="medium", choices=["low", "medium", "high", "critical"])

    task_status = task_subparsers.add_parser("status", help="Show task status")
    task_status.add_argument("task_id", help="Task ID")
    task_status.add_argument("--workspace", default=".", help="Workspace root directory")
    task_status.add_argument("--ops", action="store_true", help="Show operator-level details")

    task_replay = task_subparsers.add_parser("replay", help="Replay task events")
    task_replay.add_argument("task_id", help="Task ID")
    task_replay.add_argument("--workspace", default=".", help="Workspace root directory")

    task_export = task_subparsers.add_parser("export", help="Export task to JSONL")
    task_export.add_argument("task_id", help="Task ID")
    task_export.add_argument("--workspace", default=".", help="Workspace root directory")
    task_export.add_argument("--output", default="", help="Output file path")

    agent_parser = subparsers.add_parser("agent", help="Agent management")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)

    agent_list = agent_subparsers.add_parser("list", help="List agents")
    agent_list.add_argument("--workspace", default=".", help="Workspace root directory")

    agent_show = agent_subparsers.add_parser("show", help="Show agent details")
    agent_show.add_argument("agent_id", help="Agent ID")
    agent_show.add_argument("--workspace", default=".", help="Workspace root directory")

    queue_parser = subparsers.add_parser("queue", help="Queue management")
    queue_subparsers = queue_parser.add_subparsers(dest="queue_command", required=True)

    queue_list = queue_subparsers.add_parser("list", help="List queue state")
    queue_list.add_argument("--workspace", default=".", help="Workspace root directory")

    queue_recover = queue_subparsers.add_parser("recover", help="Recover expired leases")
    queue_recover.add_argument("--workspace", default=".", help="Workspace root directory")

    worker_parser = subparsers.add_parser("worker", help="Worker management")
    worker_subparsers = worker_parser.add_subparsers(dest="worker_command", required=True)

    worker_list = worker_subparsers.add_parser("list", help="List workers")
    worker_list.add_argument("--workspace", default=".", help="Workspace root directory")

    worker_run = worker_subparsers.add_parser("run", help="Run a worker")
    worker_run.add_argument("--kind", default="deterministic", help="Worker kind")
    worker_run.add_argument("--once", action="store_true", help="Process one item and exit")
    worker_run.add_argument("--workspace", default=".", help="Workspace root directory")

    boardroom_parser = subparsers.add_parser("boardroom", help="Boardroom session management")
    boardroom_subparsers = boardroom_parser.add_subparsers(dest="boardroom_command", required=True)

    boardroom_create = boardroom_subparsers.add_parser("create", help="Create a boardroom session")
    boardroom_create.add_argument("--title", required=True, help="Session title")
    boardroom_create.add_argument("--max-rounds", type=int, default=5)
    boardroom_create.add_argument("--workspace", default=".", help="Workspace root directory")

    boardroom_status = boardroom_subparsers.add_parser("status", help="Show boardroom status")
    boardroom_status.add_argument("session_id", help="Session ID")
    boardroom_status.add_argument("--workspace", default=".", help="Workspace root directory")

    boardroom_advance = boardroom_subparsers.add_parser("advance", help="Advance to next round")
    boardroom_advance.add_argument("session_id", help="Session ID")
    boardroom_advance.add_argument("--workspace", default=".", help="Workspace root directory")

    a2a_parser = subparsers.add_parser("a2a", help="A2A projection utilities")
    a2a_subparsers = a2a_parser.add_subparsers(dest="a2a_command", required=True)

    a2a_task = a2a_subparsers.add_parser("task", help="Show A2A task projection")
    a2a_task.add_argument("task_id", help="Task ID")
    a2a_task.add_argument("--workspace", default=".", help="Workspace root directory")

    a2a_agent = a2a_subparsers.add_parser("agent", help="Show A2A agent card projection")
    a2a_agent.add_argument("agent_id", help="Agent ID")
    a2a_agent.add_argument("--workspace", default=".", help="Workspace root directory")

    painter_parser = subparsers.add_parser("painter", help="Painter workflow")
    painter_subparsers = painter_parser.add_subparsers(dest="painter_command", required=True)

    painter_run = painter_subparsers.add_parser("run", help="Run painter workflow")
    painter_run.add_argument("task_id", help="Task ID")
    painter_run.add_argument("--purpose", default="", help="Visual purpose")
    painter_run.add_argument("--prompt", default="", help="Image prompt")
    painter_run.add_argument("--style", default="", help="Style notes")
    painter_run.add_argument("--workspace", default=".", help="Workspace root directory")

    return parser


def handle_zeus(args: argparse.Namespace) -> int:
    config = store.StoreConfig.from_workspace(getattr(args, "workspace", "."))
    conn = store.init_store(config)

    try:
        if args.zeus_command == "init":
            Path(config.artifact_root).mkdir(parents=True, exist_ok=True)
            version = schema.get_schema_version(conn)
            print(json.dumps({"ok": True, "schema_version": version, "db_path": config.db_path}, ensure_ascii=False))
            return 0

        if args.zeus_command == "doctor":
            result = doctor.run_diagnostics(config)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1

        if args.zeus_command == "task":
            return _handle_task(conn, args)

        if args.zeus_command == "agent":
            return _handle_agent(conn, args)

        if args.zeus_command == "queue":
            return _handle_queue(conn, args)

        if args.zeus_command == "worker":
            return _handle_worker(conn, config, args)

        if args.zeus_command == "boardroom":
            return _handle_boardroom(conn, args)

        if args.zeus_command == "a2a":
            return _handle_a2a(conn, args)

        if args.zeus_command == "painter":
            return _handle_painter(conn, config, args)

        return 2
    except (FileNotFoundError, KeyError, ValueError, sqlite3.IntegrityError, PermissionError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    finally:
        conn.close()


def _handle_task(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.task_command == "submit":
        task_id = ids.generate_id("task")
        now = store.now_utc()
        conn.execute(
            """
            INSERT INTO tasks (task_id, title, user_goal, state, priority, budget_json, metadata_json, revision, created_at, updated_at)
            VALUES (?, ?, ?, 'submitted', ?, '{}', '{}', 1, ?, ?)
            """,
            (task_id, args.title, args.goal, args.priority, now, now),
        )
        events.append_event(conn, task_id=task_id, event_type="task.proposed", actor_type="user", payload={"title": args.title})
        conn.commit()
        print(json.dumps({"ok": True, "task_id": task_id}, ensure_ascii=False))
        return 0

    if args.task_command == "status":
        cur = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (args.task_id,))
        row = cur.fetchone()
        if not row:
            print(json.dumps({"ok": False, "error": "Task not found"}, ensure_ascii=False))
            return 1
        result = dict(row)
        if not args.ops:
            result.pop("metadata_json", None)
        print(json.dumps({"ok": True, "task": result}, ensure_ascii=False))
        return 0

    if args.task_command == "replay":
        evts = events.get_events_for_task(conn, args.task_id)
        print(json.dumps({"ok": True, "events": evts}, ensure_ascii=False))
        return 0

    if args.task_command == "export":
        output = Path(args.output) if args.output else Path(f"data/exports/{args.task_id}.jsonl")
        result = export.export_task_jsonl(conn, args.task_id, output)
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0

    return 2


def _handle_agent(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.agent_command == "list":
        cur = conn.execute("SELECT agent_id, name, persona_type, status FROM agent_cards ORDER BY name")
        rows = [dict(r) for r in cur.fetchall()]
        print(json.dumps({"ok": True, "agents": rows}, ensure_ascii=False))
        return 0

    if args.agent_command == "show":
        cur = conn.execute("SELECT * FROM agent_cards WHERE agent_id = ?", (args.agent_id,))
        row = cur.fetchone()
        if not row:
            print(json.dumps({"ok": False, "error": "Agent not found"}, ensure_ascii=False))
            return 1
        result = dict(row)
        print(json.dumps({"ok": True, "agent": result}, ensure_ascii=False))
        return 0

    return 2


def _handle_queue(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.queue_command == "list":
        state = queue.list_queue_state(conn)
        dead = queue.list_dead_letters(conn)
        print(json.dumps({"ok": True, "queue_state": state, "dead_letters": dead}, ensure_ascii=False))
        return 0

    if args.queue_command == "recover":
        recovered = queue.recover_expired(conn)
        print(json.dumps({"ok": True, "recovered": recovered}, ensure_ascii=False))
        return 0

    return 2


def _handle_worker(conn: sqlite3.Connection, config: store.StoreConfig, args: argparse.Namespace) -> int:
    if args.worker_command == "list":
        cur = conn.execute("SELECT worker_id, agent_id, kind, display_name, status, current_work_order_id, heartbeat_at FROM worker_agents")
        rows = [dict(r) for r in cur.fetchall()]
        print(json.dumps({"ok": True, "workers": rows}, ensure_ascii=False))
        return 0

    if args.worker_command == "run":
        topic = f"worker.{args.kind}"
        lease_owner = f"cli-worker-{args.kind}"
        claimed = queue.claim_next(conn, topic, lease_owner, lease_seconds=300)
        if not claimed:
            print(json.dumps({"ok": True, "action": "no_work"}, ensure_ascii=False))
            return 0
        work_order_id = claimed["payload"].get("work_order_id")
        result = {"processed_queue_id": claimed["queue_id"], "work_order_id": work_order_id, "action": "processed"}
        queue.ack(conn, claimed["queue_id"], lease_owner, work_order_result=result)
        conn.commit()
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0

    return 2


def _handle_boardroom(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.boardroom_command == "create":
        session_id = boardroom.create_session(conn, args.title, max_rounds=args.max_rounds)
        conn.commit()
        print(json.dumps({"ok": True, "session_id": session_id}, ensure_ascii=False))
        return 0

    if args.boardroom_command == "status":
        status = boardroom.get_session_status(conn, args.session_id)
        if not status:
            print(json.dumps({"ok": False, "error": "Session not found"}, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, "session": status}, ensure_ascii=False))
        return 0

    if args.boardroom_command == "advance":
        result = boardroom.advance_round(conn, args.session_id)
        conn.commit()
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0

    return 2


def _handle_a2a(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.a2a_command == "task":
        projected = a2a.task_to_a2a(conn, args.task_id)
        if not projected:
            print(json.dumps({"ok": False, "error": "Task not found"}, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, "task": projected}, ensure_ascii=False))
        return 0

    if args.a2a_command == "agent":
        projected = a2a.agent_card_to_a2a(conn, args.agent_id)
        if not projected:
            print(json.dumps({"ok": False, "error": "Agent not found"}, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, "agent_card": projected}, ensure_ascii=False))
        return 0

    return 2


def _handle_painter(conn: sqlite3.Connection, config: store.StoreConfig, args: argparse.Namespace) -> int:
    if args.painter_command == "run":
        records = painter.run_painter_workflow(
            conn,
            Path(config.artifact_root),
            args.task_id,
            purpose=args.purpose,
            prompt=args.prompt,
            style=args.style,
        )
        conn.commit()
        print(json.dumps({"ok": True, "artifacts": [r["artifact_id"] for r in records]}, ensure_ascii=False))
        return 0

    return 2
