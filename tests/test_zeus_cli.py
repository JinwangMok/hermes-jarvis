import argparse
import json
import sqlite3
from pathlib import Path

import pytest

from jinwang_jarvis.cli import build_parser, main
from jinwang_jarvis.zeus_os import schema, store
from jinwang_jarvis.zeus_os.cli import build_zeus_parser


def _in_memory_store():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in store.DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


def _last_json(capsys):
    out = capsys.readouterr().out.strip()
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return json.loads(lines[-1])


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise AssertionError(f"no subparser action in {parser.prog}")


def _action_signature(action: argparse.Action) -> tuple[object, ...]:
    return (
        type(action).__name__,
        tuple(action.option_strings),
        action.dest,
        getattr(action, "required", False),
        action.nargs,
        action.const,
        action.default,
        tuple(action.choices) if action.choices is not None else None,
    )


def _parser_tree(parser: argparse.ArgumentParser) -> dict[str, object]:
    actions = [
        _action_signature(action)
        for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction)
    ]
    try:
        subparsers = _subparser_action(parser)
    except AssertionError:
        children = {}
    else:
        children = {name: _parser_tree(child) for name, child in sorted(subparsers.choices.items())}
    return {"actions": actions, "children": children}


class TestZeusCliParserParity:
    def test_top_level_zeus_parser_matches_standalone_zeus_parser(self):
        top_parser = build_parser()
        top_subparsers = _subparser_action(top_parser)
        top_zeus_parser = top_subparsers.choices["zeus"]

        assert _parser_tree(top_zeus_parser) == _parser_tree(build_zeus_parser())

    def test_top_level_zeus_unknown_subcommand_fails_like_standalone(self):
        with pytest.raises(SystemExit) as top_exc:
            build_parser().parse_args(["zeus", "unknown-command"])
        with pytest.raises(SystemExit) as standalone_exc:
            build_zeus_parser().parse_args(["unknown-command"])

        assert top_exc.value.code == standalone_exc.value.code == 2


class TestZeusCliInit:
    def test_init_creates_schema(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        ret = main(["zeus", "init", "--workspace", str(workspace)])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["schema_version"] >= 1
        assert Path(result["db_path"]).exists()


class TestZeusCliDoctor:
    def test_doctor_passes_on_fresh_init(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        ret = main(["zeus", "doctor", "--workspace", str(workspace)])
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["db_exists"] is True
        assert result["wal_mode"] is True
        assert result["foreign_keys"] is True


class TestZeusCliTask:
    def test_task_submit(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        ret = main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Test task", "--goal", "Do something"])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["task_id"].startswith("tsk_")

    def test_task_status(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Test task"])
        task_id = _last_json(capsys)["task_id"]
        ret = main(["zeus", "task", "status", "--workspace", str(workspace), task_id])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["task"]["title"] == "Test task"

    def test_task_replay(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Test task"])
        task_id = _last_json(capsys)["task_id"]
        ret = main(["zeus", "task", "replay", "--workspace", str(workspace), task_id])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert len(result["events"]) >= 1

    def test_task_export(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Test task"])
        task_id = _last_json(capsys)["task_id"]
        output = tmp_path / "export.jsonl"
        ret = main(["zeus", "task", "export", "--workspace", str(workspace), "--output", str(output), task_id])
        assert ret == 0
        assert output.exists()


class TestZeusCliAgent:
    def test_agent_list(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        ret = main(["zeus", "agent", "list", "--workspace", str(workspace)])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert len(result["agents"]) >= 13

    def test_agent_show(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        ret = main(["zeus", "agent", "show", "--workspace", str(workspace), "painter"])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["agent"]["name"] == "Painter"


class TestZeusCliBoardroom:
    def test_boardroom_create(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        ret = main(["zeus", "boardroom", "create", "--workspace", str(workspace), "--title", "Test session"])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["session_id"].startswith("ses_")

    def test_boardroom_advance_enforces_max_rounds(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        main(["zeus", "boardroom", "create", "--workspace", str(workspace), "--title", "Test", "--max-rounds", "2"])
        session_id = _last_json(capsys)["session_id"]
        main(["zeus", "boardroom", "advance", "--workspace", str(workspace), session_id])
        main(["zeus", "boardroom", "advance", "--workspace", str(workspace), session_id])
        ret = main(["zeus", "boardroom", "advance", "--workspace", str(workspace), session_id])
        result = _last_json(capsys)
        assert result["status"] == "closed"


class TestZeusCliA2A:
    def test_a2a_agent(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        ret = main(["zeus", "a2a", "agent", "--workspace", str(workspace), "painter"])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["agent_card"]["name"] == "Painter"

    def test_a2a_task(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Test"])
        task_id = _last_json(capsys)["task_id"]
        ret = main(["zeus", "a2a", "task", "--workspace", str(workspace), task_id])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert result["task"]["state"] == "TASK_STATE_SUBMITTED"


class TestZeusCliPainter:
    def test_painter_run(self, tmp_path, capsys):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["zeus", "init", "--workspace", str(workspace)])
        main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Visual task"])
        task_id = _last_json(capsys)["task_id"]
        ret = main(["zeus", "painter", "run", "--workspace", str(workspace), "--purpose", "test", "--prompt", "a cat", task_id])
        assert ret == 0
        result = _last_json(capsys)
        assert result["ok"] is True
        assert len(result["artifacts"]) == 3
