from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path


PLUGIN_PATH = Path(__file__).resolve().parents[1] / "plugins" / "hermes_jarvis_styled_voice_gateway" / "__init__.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("hermes_jarvis_styled_voice_gateway_under_test", PLUGIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_professor_voice_request_from_multiline_korean_command():
    plugin = load_plugin()
    request = plugin.parse_professor_voice_request("교수님 목소리로 아래 문장 음성 생성해줘\n안녕하세요. 오늘 회의를 시작하겠습니다.")
    assert request is not None
    assert request.voice == "jongwon"
    assert request.text == "안녕하세요. 오늘 회의를 시작하겠습니다."


def test_parse_professor_voice_request_from_inline_command():
    plugin = load_plugin()
    request = plugin.parse_professor_voice_request("교수님 목소리로 읽어줘: 이 방향으로 정리해 봅시다.")
    assert request is not None
    assert request.text == "이 방향으로 정리해 봅시다."


def test_short_professor_voice_request_is_expanded_with_hesitation_markers():
    plugin = load_plugin()

    request = plugin.parse_professor_voice_request("교수님 말로 만들어줘: 호? 하이닉스 들어가 말아?")

    assert request is not None
    assert request.text != "호? 하이닉스 들어가 말아?"
    assert request.text.splitlines() == [
        "어,,",
        "어...",
        "어, 호?",
        "...",
        "...",
        "하이닉스 들어가? 어...",
        "들어가 말아...?",
        "…",
        "어.....",
        "...",
    ]
    assert "뜸들이" in request.style_prompt


def test_explicit_pause_script_is_preserved():
    plugin = load_plugin()
    script = "어,,\n어...\n호?\n...\n하이닉스 들어가?"

    request = plugin.parse_professor_voice_request("교수님 목소리로 음성 생성해줘\n" + script)

    assert request is not None
    assert request.text == script


def test_parse_professor_voice_request_ignores_non_generation_mentions():
    plugin = load_plugin()
    assert plugin.parse_professor_voice_request("교수님 목소리 샘플 있나?") is None
    assert plugin.parse_professor_voice_request("/styled-voice profile=jongwon hello") is None


def test_pre_gateway_dispatch_intercepts_authorized_discord_request(monkeypatch):
    plugin = load_plugin()

    async def fake_handle(event, gateway, request):
        return None

    monkeypatch.setattr(plugin, "_handle_styled_voice_request", fake_handle)
    source = type("Source", (), {"platform": "discord", "chat_id": "channel-1"})()
    event = type("Event", (), {"text": "교수님 목소리로 음성 생성해줘\n테스트입니다.", "source": source})()

    result = plugin._pre_gateway_dispatch(event, None)

    assert result == {"action": "skip", "reason": "jarvis_styled_voice_gateway"}


def test_run_styled_voice_helper_reads_output_ogg(monkeypatch, tmp_path):
    plugin = load_plugin()
    fake_helper = tmp_path / "helper.py"
    fake_output = tmp_path / "out.ogg"
    fake_output.write_bytes(b"ogg")
    fake_helper.write_text(
        "import json\nprint(json.dumps({'output_ogg': '" + str(fake_output) + "'}))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plugin, "DEFAULT_HELPER", fake_helper)

    result = asyncio.run(plugin._run_styled_voice_helper(plugin.StyledVoiceRequest(text="hello")))

    assert result["ok"] is True
    assert result["output_ogg"] == str(fake_output)


def test_run_styled_voice_helper_accepts_pretty_json_ogg_output(monkeypatch, tmp_path):
    plugin = load_plugin()
    fake_helper = tmp_path / "helper.py"
    fake_output = tmp_path / "out.ogg"
    fake_output.write_bytes(b"ogg")
    fake_helper.write_text(
        "import json\nprint(json.dumps({'ok': True, 'ogg_output': '" + str(fake_output) + "'}, indent=2))\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plugin, "DEFAULT_HELPER", fake_helper)

    result = asyncio.run(plugin._run_styled_voice_helper(plugin.StyledVoiceRequest(text="hello")))

    assert result["ok"] is True
    assert result["output_ogg"] == str(fake_output)
