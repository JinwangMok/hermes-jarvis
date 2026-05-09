from __future__ import annotations

import importlib.util
import json
import sys
import asyncio
from pathlib import Path


PLUGIN_PATH = Path(__file__).resolve().parents[1] / "plugins" / "hermes_minerva_gateway" / "__init__.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("hermes_minerva_gateway_under_test", PLUGIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_minerva_command_accepts_aliases_and_defaults_goal():
    plugin = load_plugin()
    assert plugin.parse_minerva_command("/minerva build discord buttons").goal == "build discord buttons"
    assert plugin.parse_minerva_command("/minerva\nship it").goal == "ship it"
    assert plugin.parse_minerva_command("/minerva").goal == "Discord-origin Minerva task"
    assert plugin.parse_minerva_command("hello /minerva") is None


def test_parse_minerva_request_auto_delegates_nontrivial_boramae_messages():
    plugin = load_plugin()
    simple = ["A", "ok", "네", "ping", "/help"]
    for text in simple:
        assert plugin.parse_minerva_request(text) is None

    command = plugin.parse_minerva_request("이 설계를 검증하고 적용한 다음 보고해줘")
    assert command.goal == "이 설계를 검증하고 적용한 다음 보고해줘"
    assert command.explicit is False
    assert plugin.parse_minerva_request("짧아도 왜 실패했어?").explicit is False
    continue_requests = [
        "일어나서 하던거 계속 진행해",
        "이 작업 이어서 해줘",
        "resume the previous task",
        "continue where we left off",
    ]
    for text in continue_requests:
        assert plugin.parse_minerva_request(text) is None
    assert plugin.parse_minerva_request("오늘은 날씨가 꽤 좋고 그냥 이런저런 긴 이야기를 이어가고 있어") is None


def test_thread_name_is_bounded_sanitized_and_redacted():
    plugin = load_plugin()
    name = plugin._thread_name("<@123> `danger` / token=supersecret123 " + "x" * 200)
    assert name.startswith("Minerva · ")
    assert len(name) <= 80
    assert "`" not in name
    assert "/" not in name
    assert "supersecret123" not in name
    assert "REDACTED" in name


def test_card_text_summarizes_latest_state(tmp_path):
    plugin = load_plugin()
    card = {
        "run_id": "minerva-20260502-test",
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
    assert "minerva-20260502-test" in text
    assert "interviewing" in text
    assert "ZeusOS-owned runtime/tests only" in text
    assert "Scope: <your value>" in text
    assert "버튼" in text


def test_pre_gateway_dispatch_returns_action_skip(monkeypatch):
    plugin = load_plugin()

    async def fake_handle(event, gateway, command):
        return None

    monkeypatch.setattr(plugin, "_handle_minerva_command", fake_handle)
    source = type("Source", (), {"platform": "discord"})()
    event = type("Event", (), {"text": "/minerva audit", "source": source})()

    result = plugin._pre_gateway_dispatch(event, None)

    assert result == {"action": "skip", "reason": "minerva_gateway_bridge"}


def test_pre_gateway_dispatch_auto_delegates_nontrivial_discord_message(monkeypatch):
    plugin = load_plugin()
    captured = []

    async def fake_handle(event, gateway, command):
        captured.append(command)

    monkeypatch.setattr(plugin, "_handle_minerva_command", fake_handle)
    source = type("Source", (), {"platform": "discord"})()
    event = type("Event", (), {"text": "Minerva 기능 완성을 위해 기본 의뢰 정책을 적용하고 검증해줘", "source": source})()

    result = plugin._pre_gateway_dispatch(event, None)

    assert result == {"action": "skip", "reason": "minerva_default_delegate"}
    assert captured[0].explicit is False
    assert "기본 의뢰 정책" in captured[0].goal


def test_pre_gateway_dispatch_does_not_auto_delegate_inside_minerva_thread_or_from_bot(monkeypatch):
    plugin = load_plugin()

    async def fake_handle(event, gateway, command):
        raise AssertionError("auto-delegate should be guarded")

    monkeypatch.setattr(plugin, "_handle_minerva_command", fake_handle)
    source = type("Source", (), {"platform": "discord"})()
    minerva_channel = type("Channel", (), {"name": "Minerva · existing task", "parent": None})()
    raw_in_minerva_thread = type("RawMessage", (), {"channel": minerva_channel, "author": type("Author", (), {"bot": False})()})()
    event = type("Event", (), {"text": "Acceptance: 충분한 검증과 보고까지 진행해줘", "source": source, "raw_message": raw_in_minerva_thread})()
    assert plugin._pre_gateway_dispatch(event, None) is None

    normal_channel = type("Channel", (), {"name": "보라매봇-기본", "parent": None})()
    bot_raw = type("RawMessage", (), {"channel": normal_channel, "author": type("Author", (), {"bot": True})()})()
    bot_event = type("Event", (), {"text": "이 작업을 검증하고 보고해줘", "source": source, "raw_message": bot_raw})()
    assert plugin._pre_gateway_dispatch(bot_event, None) is None


def test_interview_reply_lists_actionable_remaining_prompts():
    plugin = load_plugin()
    text = plugin._interview_reply({
        "phase": "interviewing",
        "interaction": {"next_unresolved": ["scope", "acceptance"]},
    })
    assert "Minerva 인터뷰 계속" in text
    assert "Scope:" in text
    assert "Acceptance:" in text


def test_card_components_reads_nested_card_payload():
    plugin = load_plugin()
    card = {
        "run_id": "minerva-20260502-test",
        "card": {
            "components": [
                {"type": "button", "action": "select_proposal", "custom_id": "minerva:v2:select_proposal:minerva-20260502-test:r1:dscope:oa"},
                {"type": "button", "action": "other_opinion", "custom_id": "minerva:v2:other_opinion:minerva-20260502-test:r1:dscope:oother"},
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


def test_gateway_semantic_client_calls_hermes_cli_and_parses_json(monkeypatch):
    plugin = load_plugin()
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return type("Completed", (), {
            "returncode": 0,
            "stdout": json.dumps({
                "intent_summary": "semantic pass",
                "signals": ["llm"],
                "proposal_overrides": {},
            }),
            "stderr": "",
        })()

    monkeypatch.setattr(plugin.subprocess, "run", fake_run)
    result = plugin.HermesSubprocessSemanticUnderstandingClient().understand_minerva_goal({"goal": "x"})

    assert captured["cmd"][:3] == ["hermes", "chat", "-q"]
    assert "Return JSON only" in captured["cmd"][3]
    assert captured["kwargs"]["timeout"] == 60
    assert result["intent_summary"] == "semantic pass"
    assert result["provider"] == "hermes-cli"


def test_handle_minerva_command_creates_thread_when_invoked_from_parent_channel(monkeypatch):
    plugin = load_plugin()
    calls: list[str] = []

    class FakeService:
        def __init__(self):
            self.semantic_client = None

        def start(self, *args, **kwargs):
            calls.append("start")
            assert kwargs["auto_open_thread"] is True
            assert kwargs["origin_channel_id"] == "parent-1"
            assert kwargs["origin_thread_id"] == ""
            assert self.semantic_client is not None
            assert hasattr(self.semantic_client, "understand_minerva_goal")
            return {"run_id": "minerva-20260502-order"}

        def mark_thread_created(self, run_id, **kwargs):
            calls.append("mark")
            assert calls == ["start", "create", "mark"]
            assert kwargs["thread_id"] == "thread-1"
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

    import zeus_os.minerva as minerva

    def fake_from_config(cls, config, semantic_client=None):
        service = FakeService()
        service.semantic_client = semantic_client
        return service

    monkeypatch.setattr(minerva.MinervaWorkflow, "from_config", classmethod(fake_from_config))

    channel = type("ParentChannel", (), {"id": "parent-1", "parent": None})()
    raw_message = type("RawMessage", (), {"channel": channel, "id": "message-1", "guild": type("Guild", (), {"id": "guild-1"})()})()
    source = type("Source", (), {"thread_id": "", "chat_id": "parent-1", "platform": None})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()

    asyncio.run(plugin._handle_minerva_command(event, None, plugin.MinervaCommand(goal="credential smoke")))

    assert calls == ["start", "create", "mark", "thread.created", "render"]


def test_handle_minerva_command_reuses_gateway_spawned_current_thread(monkeypatch):
    plugin = load_plugin()
    calls: list[str] = []

    class FakeService:
        def __init__(self):
            self.semantic_client = None

        def start(self, *args, **kwargs):
            calls.append("start")
            assert kwargs["auto_open_thread"] is False
            assert kwargs["origin_channel_id"] == "parent-1"
            assert kwargs["origin_thread_id"] == "origin-thread"
            return {"run_id": "minerva-20260509-reuse"}

        def mark_thread_created(self, run_id, **kwargs):
            calls.append("mark")
            assert calls == ["start", "mark"]
            assert kwargs["thread_id"] == "origin-thread"
            assert kwargs["thread_name"] == "Hermes spawned thread"
            return {"run_id": run_id}

        def _append_interview_card(self, run_id, event):
            calls.append(event)

    async def fail_create_sibling_thread(parent, raw_message, name):
        raise AssertionError("gateway-spawned current thread must be reused, not nested")

    async def fake_render_latest_card(thread, service, run_id):
        calls.append("render")
        assert getattr(thread, "id") == "origin-thread"

    monkeypatch.setattr(plugin, "_create_sibling_thread", fail_create_sibling_thread)
    monkeypatch.setattr(plugin, "_render_latest_card", fake_render_latest_card)

    import zeus_os.minerva as minerva

    def fake_from_config(cls, config, semantic_client=None):
        service = FakeService()
        service.semantic_client = semantic_client
        return service

    monkeypatch.setattr(minerva.MinervaWorkflow, "from_config", classmethod(fake_from_config))

    parent = type("Parent", (), {"id": "parent-1"})()
    channel = type("ThreadChannel", (), {"id": "origin-thread", "name": "Hermes spawned thread", "parent": parent})()
    raw_message = type("RawMessage", (), {"channel": channel, "id": "message-1", "guild": type("Guild", (), {"id": "guild-1"})()})()
    source = type("Source", (), {"thread_id": "origin-thread", "chat_id": "origin-thread", "platform": None})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()

    asyncio.run(plugin._handle_minerva_command(event, None, plugin.MinervaCommand(goal="credential smoke")))

    assert calls == ["start", "mark", "thread.created", "render"]


def test_handle_minerva_command_reuses_source_thread_even_when_channel_parent_is_missing(monkeypatch):
    plugin = load_plugin()
    calls: list[str] = []

    class FakeService:
        def start(self, *args, **kwargs):
            calls.append("start")
            assert kwargs["auto_open_thread"] is False
            assert kwargs["origin_channel_id"] == "parent-1"
            assert kwargs["origin_thread_id"] == "origin-thread"
            return {"run_id": "minerva-20260509-source-thread"}

        def mark_thread_created(self, run_id, **kwargs):
            calls.append("mark")
            assert kwargs["thread_id"] == "origin-thread"
            return {"run_id": run_id}

        def _append_interview_card(self, run_id, event):
            calls.append(event)

    async def fail_create_sibling_thread(parent, raw_message, name):
        raise AssertionError("source.thread_id means Hermes already spawned the operating thread")

    async def fake_render_latest_card(thread, service, run_id):
        calls.append("render")
        assert getattr(thread, "id") == "origin-thread"

    monkeypatch.setattr(plugin, "_create_sibling_thread", fail_create_sibling_thread)
    monkeypatch.setattr(plugin, "_render_latest_card", fake_render_latest_card)

    import zeus_os.minerva as minerva

    monkeypatch.setattr(
        minerva.MinervaWorkflow,
        "from_config",
        classmethod(lambda cls, config, semantic_client=None: FakeService()),
    )

    channel = type("ThreadChannelWithoutParent", (), {"id": "origin-thread", "name": "Hermes spawned thread", "parent": None})()
    raw_message = type("RawMessage", (), {"channel": channel, "id": "message-1", "guild": type("Guild", (), {"id": "guild-1"})()})()
    source = type("Source", (), {"thread_id": "origin-thread", "parent_chat_id": "parent-1", "chat_id": "origin-thread", "platform": None})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()

    asyncio.run(plugin._handle_minerva_command(event, None, plugin.MinervaCommand(goal="credential smoke")))

    assert calls == ["start", "mark", "thread.created", "render"]


def test_handle_minerva_command_current_thread_renders_card_without_pointer_message(monkeypatch):
    plugin = load_plugin()
    calls: list[str] = []

    class FakeService:
        def start(self, *args, **kwargs):
            calls.append("start")
            assert kwargs["auto_open_thread"] is False
            assert kwargs["origin_channel_id"] == "parent-1"
            assert kwargs["origin_thread_id"] == "origin-thread"
            return {"run_id": "minerva-20260509-live-shape"}

        def mark_thread_created(self, run_id, **kwargs):
            calls.append("mark")
            assert kwargs["thread_id"] == "origin-thread"
            return {"run_id": run_id}

        def _append_interview_card(self, run_id, event):
            calls.append(event)

    async def fail_create_sibling_thread(parent, raw_message, name):
        raise AssertionError("current source thread must be the Minerva operating thread")

    async def fake_render_latest_card(thread, service, run_id):
        calls.append("render")
        assert getattr(thread, "id") == "origin-thread"

    class Adapter:
        async def send(self, chat_id, content):
            calls.append(f"adapter-send:{chat_id}:{content}")

    monkeypatch.setattr(plugin, "_create_sibling_thread", fail_create_sibling_thread)
    monkeypatch.setattr(plugin, "_render_latest_card", fake_render_latest_card)

    import zeus_os.minerva as minerva

    monkeypatch.setattr(
        minerva.MinervaWorkflow,
        "from_config",
        classmethod(lambda cls, config, semantic_client=None: FakeService()),
    )

    channel = type("ThreadChannelWithoutParent", (), {"id": "origin-thread", "name": "Hermes spawned thread", "parent": None})()
    raw_message = type("RawMessage", (), {"channel": channel, "id": "message-1", "guild": type("Guild", (), {"id": "guild-1"})()})()
    source = type("Source", (), {"thread_id": "origin-thread", "parent_chat_id": "parent-1", "chat_id": "origin-thread", "platform": "discord"})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()
    gateway = type("Gateway", (), {"adapters": {"discord": Adapter()}})()

    asyncio.run(plugin._handle_minerva_command(event, gateway, plugin.MinervaCommand(goal="live shape")))

    assert calls == ["start", "mark", "thread.created", "render"]



def test_handle_minerva_command_resolves_hermes_autothread_before_rendering(monkeypatch):
    plugin = load_plugin()
    calls: list[str] = []

    class FakeService:
        def start(self, *args, **kwargs):
            calls.append("start")
            assert kwargs["auto_open_thread"] is False
            assert kwargs["origin_channel_id"] == "parent-1"
            assert kwargs["origin_thread_id"] == "origin-thread"
            return {"run_id": "minerva-20260509-parent-mismatch"}

        def mark_thread_created(self, run_id, **kwargs):
            calls.append("mark")
            assert kwargs["thread_id"] == "origin-thread"
            assert kwargs["thread_name"] == "Hermes spawned thread"
            return {"run_id": run_id}

        def _append_interview_card(self, run_id, event):
            calls.append(event)

    class ParentChannel:
        id = "parent-1"
        name = "보라매봇-기본"
        parent = None

        def get_thread(self, thread_id):
            calls.append(f"parent-get-thread:{thread_id}")
            return None

        async def create_thread(self, *args, **kwargs):
            raise AssertionError("source.thread_id must not create a sibling/nested thread")

        async def send(self, *args, **kwargs):
            raise AssertionError("Minerva card must not leak to parent channel")

    parent = ParentChannel()
    thread = type("Thread", (), {"id": "origin-thread", "name": "Hermes spawned thread", "parent": parent, "parent_id": "parent-1"})()

    class Guild:
        id = "guild-1"

        def get_thread(self, thread_id):
            calls.append(f"guild-get-thread:{thread_id}")
            return thread

    async def fail_create_sibling_thread(parent, raw_message, name):
        raise AssertionError("source.thread_id means Hermes already spawned the operating thread")

    async def fake_render_latest_card(render_thread, service, run_id):
        calls.append("render")
        assert render_thread is thread

    monkeypatch.setattr(plugin, "_create_sibling_thread", fail_create_sibling_thread)
    monkeypatch.setattr(plugin, "_render_latest_card", fake_render_latest_card)

    import zeus_os.minerva as minerva

    monkeypatch.setattr(minerva.MinervaWorkflow, "from_config", classmethod(lambda cls, config, semantic_client=None: FakeService()))

    raw_message = type("RawMessage", (), {"channel": parent, "id": "message-1", "guild": Guild()})()
    source = type("Source", (), {"thread_id": "origin-thread", "parent_chat_id": "parent-1", "chat_id": "origin-thread", "platform": "discord"})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()
    gateway = type("Gateway", (), {"adapters": {"discord": type("Adapter", (), {})()}})()

    asyncio.run(plugin._handle_minerva_command(event, gateway, plugin.MinervaCommand(goal="live mismatch")))

    assert calls == ["parent-get-thread:origin-thread", "guild-get-thread:origin-thread", "start", "mark", "thread.created", "render"]


def test_handle_minerva_command_unresolved_source_thread_fails_closed(monkeypatch):
    plugin = load_plugin()
    calls: list[str] = []

    class FakeService:
        def start(self, *args, **kwargs):
            raise AssertionError("Minerva run must not start until the Discord thread object is resolved")

    class ParentChannel:
        id = "parent-1"
        name = "보라매봇-기본"
        parent = None

        def get_thread(self, thread_id):
            return None

        async def create_thread(self, *args, **kwargs):
            raise AssertionError("unresolved source thread must not create a sibling/nested thread")

        async def send(self, *args, **kwargs):
            raise AssertionError("fail-closed diagnostic must not use parent channel.send")

    class Guild:
        id = "guild-1"

        def get_thread(self, thread_id):
            return None

        def get_channel(self, thread_id):
            return None

        async def fetch_channel(self, thread_id):
            raise LookupError("not found")

    class Adapter:
        async def send(self, chat_id, content):
            calls.append((chat_id, content))

    async def fake_render_latest_card(thread, service, run_id):
        raise AssertionError("unresolved source thread must not render")

    monkeypatch.setattr(plugin, "_render_latest_card", fake_render_latest_card)
    import zeus_os.minerva as minerva
    monkeypatch.setattr(minerva.MinervaWorkflow, "from_config", classmethod(lambda cls, config, semantic_client=None: FakeService()))

    parent = ParentChannel()
    raw_message = type("RawMessage", (), {"channel": parent, "id": "message-1", "guild": Guild()})()
    source = type("Source", (), {"thread_id": "origin-thread", "parent_chat_id": "parent-1", "chat_id": "origin-thread", "platform": "discord"})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()
    gateway = type("Gateway", (), {"adapters": {"discord": Adapter()}})()

    asyncio.run(plugin._handle_minerva_command(event, gateway, plugin.MinervaCommand(goal="live mismatch")))

    assert calls == [("origin-thread", "Minerva: Discord thread 객체를 확인하지 못해 작업을 시작하지 않았습니다.")]


def test_resolve_existing_discord_thread_rejects_wrong_parent(monkeypatch):
    plugin = load_plugin()
    parent = type("Parent", (), {"id": "parent-1", "parent": None})()
    wrong_parent = type("Parent", (), {"id": "wrong-parent"})()
    thread = type("Thread", (), {"id": "origin-thread", "name": "wrong", "parent": wrong_parent, "parent_id": "wrong-parent"})()

    class Guild:
        def get_thread(self, thread_id):
            return thread

        async def fetch_channel(self, thread_id):
            return thread

    raw_message = type("RawMessage", (), {"channel": parent, "guild": Guild()})()
    resolved = asyncio.run(plugin._resolve_existing_discord_thread(raw_message, parent, None, "origin-thread", "parent-1"))
    assert resolved is None


def test_handle_minerva_command_rejects_parent_channel_even_if_id_matches_source_thread(monkeypatch):
    plugin = load_plugin()
    calls: list[tuple[str, str] | str] = []

    class FakeService:
        def start(self, *args, **kwargs):
            raise AssertionError("parent channel masquerading as source thread must fail closed")

    class ParentChannel:
        id = "parent-1"
        name = "보라매봇-기본"
        parent = None

        async def send(self, *args, **kwargs):
            raise AssertionError("Minerva card/diagnostic must not use parent channel.send")

    class Adapter:
        async def send(self, chat_id, content):
            calls.append((chat_id, content))

    async def fake_render_latest_card(thread, service, run_id):
        raise AssertionError("parent channel must not be accepted as render target")

    monkeypatch.setattr(plugin, "_render_latest_card", fake_render_latest_card)
    import zeus_os.minerva as minerva
    monkeypatch.setattr(minerva.MinervaWorkflow, "from_config", classmethod(lambda cls, config, semantic_client=None: FakeService()))

    parent = ParentChannel()
    raw_message = type("RawMessage", (), {"channel": parent, "id": "message-1", "guild": None})()
    source = type("Source", (), {"thread_id": "parent-1", "parent_chat_id": "", "chat_id": "parent-1", "platform": "discord"})()
    event = type("Event", (), {"raw_message": raw_message, "source": source})()
    gateway = type("Gateway", (), {"adapters": {"discord": Adapter()}})()

    asyncio.run(plugin._handle_minerva_command(event, gateway, plugin.MinervaCommand(goal="bad source")))

    assert calls == [("parent-1", "Minerva: Discord thread 객체를 확인하지 못해 작업을 시작하지 않았습니다.")]
