from __future__ import annotations

import importlib.util
import json
import sys
import asyncio
from pathlib import Path


PLUGIN_PATH = Path(__file__).resolve().parents[1] / "plugins" / "hermes_hooo_gateway" / "__init__.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("hermes_hooo_gateway_under_test", PLUGIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_hooo_command_accepts_aliases_and_defaults_goal():
    plugin = load_plugin()
    assert plugin.parse_hooo_command("/hooo build discord buttons").goal == "build discord buttons"
    assert plugin.parse_hooo_command("/houroboros\nship it").goal == "ship it"
    assert plugin.parse_hooo_command("/hooo").goal == "Discord-origin HOOO task"
    assert plugin.parse_hooo_command("hello /hooo") is None


def test_thread_name_is_bounded_sanitized_and_redacted():
    plugin = load_plugin()
    name = plugin._thread_name("<@123> `danger` / token=supersecret123 " + "x" * 200)
    assert name.startswith("HOOO · ")
    assert len(name) <= 80
    assert "`" not in name
    assert "/" not in name
    assert "supersecret123" not in name
    assert "REDACTED" in name


def test_card_text_summarizes_latest_state(tmp_path):
    plugin = load_plugin()
    card = {
        "run_id": "hooo-20260502-test",
        "card": {
            "phase": "interviewing",
            "unresolved": ["scope", "acceptance"],
            "proposal_card": {
                "dimension": "scope",
                "label": "Scope",
                "proposals": [
                    {"option_id": "a", "label": "ZeusOS-owned", "value": "ZeusOS-owned runtime/tests only"},
                    {"option_id": "b", "label": "Seed only", "value": "Seed and plan only"},
                    {"option_id": "c", "label": "Tests only", "value": "Regression tests only"},
                ],
                "other": {"expected_reply": "Scope: <your value>"},
            },
        },
    }
    text = plugin._card_text(card)
    assert "hooo-20260502-test" in text
    assert "interviewing" in text
    assert "ZeusOS-owned runtime/tests only" in text
    assert "Scope: <your value>" in text
    assert "버튼" in text


def test_pre_gateway_dispatch_returns_action_skip(monkeypatch):
    plugin = load_plugin()

    async def fake_handle(event, gateway, command):
        return None

    monkeypatch.setattr(plugin, "_handle_hooo_command", fake_handle)
    source = type("Source", (), {"platform": "discord"})()
    event = type("Event", (), {"text": "/hooo audit", "source": source})()

    result = plugin._pre_gateway_dispatch(event, None)

    assert result == {"action": "skip", "reason": "hooo_gateway_bridge"}


def test_interview_reply_lists_actionable_remaining_prompts():
    plugin = load_plugin()
    text = plugin._interview_reply({
        "phase": "interviewing",
        "interaction": {"next_unresolved": ["scope", "acceptance"]},
    })
    assert "HOOO 인터뷰 계속" in text
    assert "Scope:" in text
    assert "Acceptance:" in text


def test_card_components_reads_nested_card_payload():
    plugin = load_plugin()
    card = {
        "run_id": "hooo-20260502-test",
        "card": {
            "components": [
                {"type": "button", "action": "select_proposal", "custom_id": "hooo:v2:select_proposal:hooo-20260502-test:r1:dscope:oa"},
                {"type": "button", "action": "other_opinion", "custom_id": "hooo:v2:other_opinion:hooo-20260502-test:r1:dscope:oother"},
            ]
        },
    }
    assert [component["action"] for component in plugin._card_components(card)] == ["select_proposal", "other_opinion"]


def test_latest_card_reads_last_jsonl_record(tmp_path):
    plugin = load_plugin()

    class Service:
        def _artifact_path(self, run_id: str, name: str):
            path = tmp_path / run_id / name
            path.parent.mkdir(parents=True, exist_ok=True)
            return path

    service = Service()
    path = service._artifact_path("run-1", "discord_cards.jsonl")
    path.write_text(json.dumps({"card_revision": 1}) + "\n" + json.dumps({"card_revision": 2}) + "\n", encoding="utf-8")
    assert plugin._latest_card(service, "run-1") == {"card_revision": 2}


def test_handle_hooo_command_reserves_run_before_creating_live_thread(monkeypatch):
    plugin = load_plugin()
    calls: list[str] = []

    class FakeService:
        def start(self, *args, **kwargs):
            calls.append("start")
            assert kwargs["auto_open_thread"] is True
            return {"run_id": "hooo-20260502-order"}

        def mark_thread_created(self, run_id, **kwargs):
            calls.append("mark")
            assert calls == ["start", "create", "mark"]
            return {"run_id": run_id}

        def _append_interview_card(self, run_id, event):
            calls.append(event)

    async def fake_create_sibling_thread(parent, raw_message, name):
        calls.append("create")
        return type("Thread", (), {"id": "thread-1", "name": name})()

    async def fake_render_latest_card(thread, service, run_id):
        calls.append("render")

    monkeypatch.setattr(plugin, "_create_sibling_thread", fake_create_sibling_thread)
    monkeypatch.setattr(plugin, "_render_latest_card", fake_render_latest_card)

    import zeus_os.houroboros as houroboros

    monkeypatch.setattr(houroboros.HouroborosWorkflow, "from_config", classmethod(lambda cls, config: FakeService()))

    parent = type("Parent", (), {"id": "parent-1"})()
    channel = type("ThreadChannel", (), {"parent": parent})()
    raw_message = type("RawMessage", (), {"channel": channel, "id": "message-1", "guild": type("Guild", (), {"id": "guild-1"})()})()
    source = type("Source", (), {"thread_id": "origin-thread", "chat_id": "origin-thread", "platform": None})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()

    asyncio.run(plugin._handle_hooo_command(event, None, plugin.HoooCommand(goal="token=supersecret123 smoke")))

    assert calls == ["start", "create", "mark", "thread.created", "render"]
