"""Jarvis-owned Discord bridge for natural-language styled voice requests.

This stays in the Jarvis layer. Hermes remains the gateway/plugin host; Jarvis owns
trigger parsing, the `jongwon` profile default, and the VoxCPM helper invocation.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent
JARVIS_ROOT = PLUGIN_ROOT.parents[1]
SRC_ROOT = JARVIS_ROOT / "src"
DEFAULT_HELPER = JARVIS_ROOT / "skills" / "styled-voice" / "scripts" / "styled_voice_request.py"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

_PROFESSOR_TRIGGER_RE = re.compile(r"교수님\s*(?:목소리(?:로|처럼|톤으로)?|말(?:로|투로|처럼)?)", re.I)
_PROFESSORIZE_TRIGGER_RE = re.compile(r"교수님\s*말(?:로|투로|처럼)?", re.I)
_VOICE_ACTION_RE = re.compile(r"(음성\s*생성|생성해\s*줘|읽어\s*줘|말해\s*줘|녹음해\s*줘|만들어\s*줘|tts|TTS)", re.I)
_PREFIX_CLEAN_RE = re.compile(
    r"^\s*(?:교수님\s*(?:목소리(?:로|처럼|톤으로)?|말(?:로|투로|처럼)?)\s*)?"
    r"(?:아래\s*)?(?:문장|텍스트|내용|스크립트)?(?:을|를)?\s*"
    r"(?:음성\s*)?(?:생성해\s*줘|생성|읽어\s*줘|말해\s*줘|녹음해\s*줘|만들어\s*줘|tts|TTS)?\s*[:：-]?\s*",
    re.I,
)
_DEFAULT_STYLE_PROMPT = "calm, careful, conversational, professor-like Korean explanation tone"
_PROFESSOR_HESITATION_STYLE_PROMPT = (
    "많이 뜸들이면서 말하는 스타일, 아주 느리게, 망설이듯, 긴 침묵과 작은 추임새, "
    "hesitant, long pauses, slow conversational pacing"
)


@dataclass(frozen=True)
class StyledVoiceRequest:
    text: str
    voice: str = "jongwon"
    style_prompt: str = _DEFAULT_STYLE_PROMPT


def register(api: Any) -> None:
    api.register_hook("pre_gateway_dispatch", _pre_gateway_dispatch)


def parse_professor_voice_request(text: str) -> StyledVoiceRequest | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("/styled-voice"):
        return None
    if not _PROFESSOR_TRIGGER_RE.search(raw):
        return None
    if not _VOICE_ACTION_RE.search(raw):
        return None

    lines = raw.splitlines()
    if len(lines) > 1:
        body = "\n".join(line for line in lines[1:] if line.strip()).strip()
    else:
        body = _PREFIX_CLEAN_RE.sub("", raw, count=1).strip()

    body = body.strip("` \n\t\r:：-—")
    if not body:
        return StyledVoiceRequest(text="")
    if _PROFESSORIZE_TRIGGER_RE.search(raw):
        return StyledVoiceRequest(text=_expand_professor_hesitation_script(body), style_prompt=_PROFESSOR_HESITATION_STYLE_PROMPT)
    return StyledVoiceRequest(text=body)


def _expand_professor_hesitation_script(text: str) -> str:
    body = (text or "").strip()
    if not body or _looks_like_explicit_voice_script(body):
        return body

    clauses = [part.strip() for part in re.findall(r"[^?!.。！？]+[?!.。！？]?", body) if part.strip()]
    if not clauses:
        clauses = [body]

    expanded: list[str] = ["어,,", "어..."]
    first = clauses[0]
    expanded.append(first if first.startswith("어") else f"어, {first}")
    expanded.extend(["...", "..."])

    for clause in clauses[1:]:
        split = re.match(r"^(?P<subject>.+?)\s*들어가\s*말아\??$", clause)
        if split:
            subject = split.group("subject").strip()
            expanded.append(f"{subject} 들어가? 어...")
            expanded.append("들어가 말아...?")
        else:
            expanded.append(_soften_question_for_hesitation(clause))

    expanded.extend(["…", "어.....", "..."])
    return "\n".join(expanded)


def _looks_like_explicit_voice_script(text: str) -> bool:
    if "\n" in text:
        return True
    if "..." in text or "…" in text:
        return True
    return bool(re.search(r"\b어\s*[,\.]{1,}", text))


def _soften_question_for_hesitation(clause: str) -> str:
    stripped = clause.strip()
    if stripped.endswith("?"):
        return stripped[:-1].rstrip() + "...?"
    if stripped.endswith("."):
        return stripped[:-1].rstrip() + "..."
    return stripped + "..."


def _pre_gateway_dispatch(event: Any = None, gateway: Any = None, **_: Any) -> dict[str, Any] | None:
    request = parse_professor_voice_request(getattr(event, "text", ""))
    if request is None:
        return None
    source = getattr(event, "source", None)
    if str(getattr(getattr(source, "platform", None), "value", getattr(source, "platform", ""))) != "discord":
        return None
    if gateway is not None and hasattr(gateway, "_is_user_authorized") and not gateway._is_user_authorized(source):
        return {"action": "skip", "reason": "unauthorized_jarvis_styled_voice"}
    try:
        asyncio.get_running_loop().create_task(_handle_styled_voice_request(event, gateway, request))
    except RuntimeError:
        asyncio.run(_handle_styled_voice_request(event, gateway, request))
    return {"action": "skip", "reason": "jarvis_styled_voice_gateway"}


async def _handle_styled_voice_request(event: Any, gateway: Any, request: StyledVoiceRequest) -> None:
    source = getattr(event, "source", None)
    adapter = getattr(gateway, "adapters", {}).get(getattr(source, "platform", None)) if gateway is not None else None
    raw_message = getattr(event, "raw_message", None)
    channel = getattr(raw_message, "channel", None)
    chat_id = str(getattr(source, "chat_id", "") or "")

    if not request.text:
        await _safe_send(adapter, chat_id, "교수님 목소리로 생성할 문장을 같이 보내주세요.")
        return

    await _safe_send(adapter, chat_id, "Jarvis styled-voice: `jongwon/default` 프로필로 음성 생성 중입니다.")
    result = await _run_styled_voice_helper(request)
    if not result.get("ok"):
        await _safe_send(adapter, chat_id, f"Jarvis styled-voice 생성 실패: {result.get('error', 'unknown error')}")
        return

    output = Path(str(result["output_ogg"])).expanduser()
    if not output.exists() or output.stat().st_size <= 0:
        await _safe_send(adapter, chat_id, "Jarvis styled-voice 생성 결과 파일을 확인하지 못했습니다.")
        return
    await _send_discord_file(channel, adapter, chat_id, output, "교수님 목소리 음성 생성 완료")


async def _run_styled_voice_helper(request: StyledVoiceRequest) -> dict[str, Any]:
    if not DEFAULT_HELPER.exists():
        return {"ok": False, "error": f"helper not found: {DEFAULT_HELPER}"}
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(DEFAULT_HELPER),
        "--voice",
        request.voice,
        "--input",
        request.text,
        "--style-prompt",
        request.style_prompt,
        cwd=str(JARVIS_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = (stderr or stdout).decode("utf-8", errors="replace").strip()
        return {"ok": False, "error": err[-1000:] or f"helper exited {proc.returncode}"}
    text = stdout.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(text)
    except Exception:
        payload = None
        for line in reversed(text.splitlines()):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
                break
            except Exception:
                continue
        if payload is None:
            return {"ok": False, "error": f"helper returned non-json output: {text[-1000:]}"}
    output_ogg = payload.get("output_ogg") or payload.get("ogg_output") or payload.get("ogg_path") or payload.get("output")
    if not output_ogg:
        return {"ok": False, "error": f"helper JSON missing output_ogg: {payload}"}
    return {"ok": True, "output_ogg": output_ogg, "payload": payload}


async def _send_discord_file(channel: Any, adapter: Any, chat_id: str, path: Path, content: str) -> None:
    if channel is not None:
        try:
            import discord

            await channel.send(content, file=discord.File(str(path)))
            return
        except Exception:
            pass
    await _safe_send(adapter, chat_id, f"{content}\nMEDIA:{path}")


async def _safe_send(adapter: Any, chat_id: str, content: str) -> None:
    if adapter is None or not chat_id:
        return
    try:
        await adapter.send(str(chat_id), content)
    except Exception:
        return
