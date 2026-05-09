"""Hermes plugin bridge for ZeusOS Minerva Discord UX.

Source-untouched integration: keep this in the ZeusOS repo and symlink/copy the
plugin directory into ~/.hermes/plugins only when the operator approves a gateway
restart. The plugin intercepts `/minerva ...` and `/minerva ...` Discord text
commands, reuses an already gateway-spawned Discord thread or creates a task
thread from a parent channel, starts a ZeusOS Minerva run, renders the
latest `discord_cards.jsonl` record as Discord buttons, and reduces button
clicks through `MinervaWorkflow.handle_interaction()`.
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|passwd|token|authorization)\b\s*[:=]\s*([^\s,;]+)"
)

PLUGIN_ROOT = Path(__file__).resolve().parent
ZEUSOS_ROOT = PLUGIN_ROOT.parents[1]
SRC_ROOT = ZEUSOS_ROOT / "src"
DEFAULT_CONFIG = ZEUSOS_ROOT / "config" / "pipeline.yaml"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

_COMMAND_RE = re.compile(r"^/minerva(?:\s+(?P<goal>.+))?$", re.I | re.S)
_AUTO_DELEGATE_RE = re.compile(
    r"(해줘|진행|구현|수정|고쳐|패치|검증|테스트|리뷰|조사|찾아|분석|설계|정리|비교|추천|"
    r"왜|어떻게|무엇|뭐가|가능|해야|만들|적용|완성|보고|"
    r"implement|fix|patch|verify|test|review|research|analy[sz]e|design|compare|recommend)",
    re.I,
)
_SIMPLE_TEXT_RE = re.compile(
    r"^(a|b|c|ㅇㅋ|오케이|ok|okay|네|넵|응|아니|ㄴㄴ|감사|고마워|hi|hello|ping|test|테스트)[.!?\s]*$",
    re.I,
)
_CONTINUE_RESUME_RE = re.compile(
    r"(계속\s*(해|진행|이어|하라)|하던\s*거|하던거|이어\s*(가|서|줘|해)|이어서|일어나서\s*계속|"
    r"resume|continue|pick\s+up|carry\s+on)",
    re.I,
)
_MAX_THREAD_NAME = 80


@dataclass(frozen=True)
class MinervaCommand:
    goal: str
    explicit: bool = True


class HermesSubprocessSemanticUnderstandingClient:
    """Actual LLM/API semantic pass, wrapped by Minerva's deterministic validators."""

    timeout_seconds = 60

    def understand_minerva_goal(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "You are the semantic-understanding pass for ZeusOS Minerva. "
            "Return JSON only, matching the requested schema. Do not execute tools or side effects.\n\n"
            f"REQUEST_JSON:\n{json.dumps(request, ensure_ascii=False, sort_keys=True)}"
        )
        try:
            completed = subprocess.run(
                ["hermes", "chat", "-q", prompt],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            return {
                "provider": "hermes-cli",
                "model": "configured-main-model",
                "intent_summary": "",
                "signals": [],
                "proposal_overrides": {},
                "error": _redact_text(str(exc)),
            }
        text = (completed.stdout or "").strip()
        match = re.search(r"\{.*\}", text, re.S)
        if completed.returncode != 0 or not match:
            return {
                "provider": "hermes-cli",
                "model": "configured-main-model",
                "intent_summary": "",
                "signals": [],
                "proposal_overrides": {},
                "error": _redact_text((completed.stderr or text)[-500:]),
            }
        payload = json.loads(match.group(0))
        if isinstance(payload, dict):
            payload.setdefault("provider", "hermes-cli")
            payload.setdefault("model", "configured-main-model")
            return payload
        return {"provider": "hermes-cli", "model": "configured-main-model", "intent_summary": "", "signals": [], "proposal_overrides": {}}


def register(api: Any) -> None:
    api.register_hook("pre_gateway_dispatch", _pre_gateway_dispatch)


def parse_minerva_command(text: str) -> MinervaCommand | None:
    match = _COMMAND_RE.match((text or "").strip())
    if not match:
        return None
    goal = (match.group("goal") or "").strip()
    if not goal:
        goal = "Discord-origin Minerva task"
    return MinervaCommand(goal=goal, explicit=True)


def should_auto_delegate_to_minerva(text: str) -> bool:
    """Default-route non-trivial Boramae Discord requests into Minerva.

    This hook must stay deterministic and local: no model calls inside gateway
    dispatch. Short acknowledgements/choice replies stay in the normal gateway;
    task-like or question-like messages become Minerva agendas.
    """
    normalized = " ".join((text or "").strip().split())
    if not normalized or normalized.startswith("/") or _SIMPLE_TEXT_RE.match(normalized):
        return False
    if _CONTINUE_RESUME_RE.search(normalized):
        return False
    return bool("?" in normalized or _AUTO_DELEGATE_RE.search(normalized))


def parse_minerva_request(text: str) -> MinervaCommand | None:
    explicit = parse_minerva_command(text)
    if explicit is not None:
        return explicit
    if should_auto_delegate_to_minerva(text):
        return MinervaCommand(goal=text.strip(), explicit=False)
    return None


def _is_minerva_thread_event(event: Any) -> bool:
    raw_message = getattr(event, "raw_message", None)
    channel = getattr(raw_message, "channel", None)
    name = str(getattr(channel, "name", "") or "")
    parent_name = str(getattr(getattr(channel, "parent", None), "name", "") or "")
    return name.startswith("Minerva ·") or parent_name.startswith("Minerva ·")


def _is_bot_event(event: Any) -> bool:
    raw_message = getattr(event, "raw_message", None)
    author = getattr(raw_message, "author", None)
    return bool(getattr(author, "bot", False) or getattr(event, "is_bot", False))


def _redact_text(value: str) -> str:
    return _SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def _thread_name(goal: str) -> str:
    safe = re.sub(r"[\s\n\r\t]+", " ", _redact_text(goal)).strip()
    safe = re.sub(r"[`*_~<>@#:/\\]", "", safe)
    if not safe:
        safe = "Minerva task"
    name = f"Minerva · {safe}"
    return name[: _MAX_THREAD_NAME - 1] + "…" if len(name) > _MAX_THREAD_NAME else name


def _pre_gateway_dispatch(event: Any = None, gateway: Any = None, **_: Any) -> dict[str, Any] | None:
    command = parse_minerva_request(getattr(event, "text", ""))
    if not command:
        return None
    if not command.explicit and (_is_bot_event(event) or _is_minerva_thread_event(event)):
        return None
    source = getattr(event, "source", None)
    if str(getattr(getattr(source, "platform", None), "value", getattr(source, "platform", ""))) != "discord":
        return None
    if gateway is not None and hasattr(gateway, "_is_user_authorized") and not gateway._is_user_authorized(source):
        return {"action": "skip", "reason": "unauthorized_minerva_command"}
    try:
        asyncio.get_running_loop().create_task(_handle_minerva_command(event, gateway, command))
    except RuntimeError:
        asyncio.run(_handle_minerva_command(event, gateway, command))
    reason = "minerva_gateway_bridge" if command.explicit else "minerva_default_delegate"
    return {"action": "skip", "reason": reason}


async def _handle_minerva_command(event: Any, gateway: Any, command: MinervaCommand) -> None:
    raw_message = getattr(event, "raw_message", None)
    source = getattr(event, "source", None)
    adapter = getattr(gateway, "adapters", {}).get(getattr(source, "platform", None)) if gateway is not None else None
    channel = getattr(raw_message, "channel", None)
    if channel is None:
        await _safe_send(adapter, getattr(source, "chat_id", ""), "Minerva: Discord channel을 확인하지 못했습니다.")
        return
    parent = getattr(channel, "parent", None) or channel
    if parent.__class__.__name__ == "DMChannel":
        await _safe_send(adapter, getattr(source, "chat_id", ""), "Minerva는 서버 텍스트 채널/스레드에서만 thread를 만들 수 있습니다.")
        return

    source_thread_id = str(getattr(source, "thread_id", "") or "")
    source_parent_id = str(getattr(source, "parent_chat_id", "") or "")
    parent_id = source_parent_id or str(getattr(parent, "id", getattr(source, "chat_id", "") or ""))
    current_thread_id = source_thread_id or str(getattr(channel, "id", "") or "")
    current_is_thread = bool(source_thread_id or (getattr(channel, "parent", None) is not None and current_thread_id))
    thread_name = _thread_name(command.goal)

    from zeus_os.config import load_pipeline_config
    from zeus_os.minerva import MinervaWorkflow

    service = MinervaWorkflow.from_config(load_pipeline_config(DEFAULT_CONFIG), semantic_client=HermesSubprocessSemanticUnderstandingClient())
    status = await asyncio.to_thread(
        service.start,
        command.goal,
        origin_platform="discord",
        origin_channel_id=parent_id,
        origin_thread_id=current_thread_id if current_is_thread else source_thread_id,
        origin_message_id=str(getattr(raw_message, "id", "") or ""),
        auto_open_thread=not current_is_thread,
        thread_name=getattr(channel, "name", "") if current_is_thread else thread_name,
    )
    if current_is_thread:
        thread = channel
        thread_id = current_thread_id
    else:
        thread = await _create_sibling_thread(parent, raw_message, thread_name)
        thread_id = str(getattr(thread, "id", ""))
    status = service.mark_thread_created(
        status["run_id"],
        thread_id=thread_id,
        thread_name=getattr(thread, "name", "") or thread_name,
        jump_url=f"https://discord.com/channels/{getattr(getattr(raw_message, 'guild', None), 'id', '')}/{thread_id}" if thread_id else "",
    )
    service._append_interview_card(status["run_id"], "thread.created")
    await _render_latest_card(thread, service, status["run_id"])
    verb = "사용" if current_is_thread else "생성"
    await _safe_send(adapter, getattr(source, "chat_id", parent_id), f"Minerva thread {verb}: <#{thread_id}> (`{status['run_id']}`)")


async def _create_sibling_thread(parent: Any, raw_message: Any, name: str) -> Any:
    try:
        return await parent.create_thread(name=name, auto_archive_duration=1440, reason="Minerva task thread")
    except Exception:
        seed = await parent.send(f"🌀 Minerva task: **{name}**")
        return await seed.create_thread(name=name, auto_archive_duration=1440, reason="Minerva task thread fallback")


def _latest_card(service: Any, run_id: str) -> dict[str, Any]:
    path = service._artifact_path(run_id, "discord_cards.jsonl")
    last: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = json.loads(line)
    return last


def _card_payload(card: dict[str, Any]) -> dict[str, Any]:
    payload = card.get("card") or card.get("state") or {}
    return payload if isinstance(payload, dict) else {}


def _card_components(card: dict[str, Any]) -> list[dict[str, Any]]:
    payload_components = _card_payload(card).get("components")
    if isinstance(payload_components, list):
        return payload_components
    legacy_components = card.get("components")
    return legacy_components if isinstance(legacy_components, list) else []


def _card_text(card: dict[str, Any]) -> str:
    run_id = card.get("run_id", "")
    payload = _card_payload(card)
    unresolved = payload.get("unresolved") or []
    raw_proposal_card = payload.get("proposal_card")
    proposal_card = raw_proposal_card if isinstance(raw_proposal_card, dict) else {}
    phase = payload.get("phase") or card.get("phase") or "unknown"
    lines = [f"🌀 **Minerva** `{run_id}`", f"phase: `{phase}`"]
    if proposal_card:
        lines.append(f"\n선택할 항목: **{proposal_card.get('label', proposal_card.get('dimension', 'Minerva'))}**")
        raw_proposals = proposal_card.get("proposals")
        proposals = raw_proposals if isinstance(raw_proposals, list) else []
        for proposal in proposals[:3]:
            lines.append(f"- {str(proposal.get('option_id', '')).upper()}: {proposal.get('label', '')} — {proposal.get('value', '')}")
        other = proposal_card.get("other") if isinstance(proposal_card.get("other"), dict) else {}
        if other:
            lines.append(f"- Other: {other.get('expected_reply', 'new opinion')}")
    if unresolved:
        lines.append("\n질문/모호성:")
        lines.extend(f"- {item}" for item in unresolved[:6])
        lines.append("\n버튼으로 제안을 선택하거나 다음 형식으로 직접 답하면 인터뷰가 진행됩니다:")
        lines.extend(f"- `{_dimension_prompt(item)}`" for item in unresolved[:3])
    else:
        lines.append("\nSeed 생성 가능 상태입니다.")
    return "\n".join(lines)


def _dimension_prompt(dimension: str) -> str:
    return {
        "scope": "Scope: 이번 Minerva가 다룰 범위와 제외 범위",
        "acceptance": "Acceptance: 완료로 인정할 산출물/검증 기준",
        "constraint": "Constraint: 건드리면 안 되는 파일·서비스·권한",
        "executor": "Executor: boramae / claude-code / opencode 등 실행 주체",
        "permission": "Permission: read-only, seed 승인, 구현 승인 여부",
    }.get(dimension, f"{dimension}: ...")


def _interview_reply(result: dict[str, Any]) -> str:
    interaction = result.get("interaction") or {}
    unresolved = interaction.get("next_unresolved") or result.get("interview_state", {}).get("unresolved") or []
    if not unresolved:
        return f"Minerva 처리됨: `{result['phase']}` — Seed 생성 가능 상태입니다."
    prompts = "\n".join(f"- `{_dimension_prompt(item)}`" for item in unresolved[:5])
    return f"Minerva 인터뷰 계속: `{result['phase']}`\n남은 항목:\n{prompts}"


async def _render_latest_card(thread: Any, service: Any, run_id: str) -> None:
    card = _latest_card(service, run_id)
    view = _build_view(service, card)
    await thread.send(_card_text(card), view=view)


def _build_view(service: Any, card: dict[str, Any]) -> Any:
    import discord

    class MinervaView(discord.ui.View):
        def __init__(self) -> None:
            super().__init__(timeout=None)
            for component in _card_components(card):
                if component.get("type") != "button":
                    continue
                button = discord.ui.Button(
                    label=component.get("label", component.get("action", "Minerva")),
                    custom_id=component.get("custom_id"),
                    style=_button_style(discord, component.get("style", "secondary")),
                    disabled=bool(component.get("disabled", False)),
                )
                button.callback = self._callback_for(component)
                self.add_item(button)

        def _callback_for(self, component: dict[str, Any]):
            async def _callback(interaction: Any) -> None:
                run_id = card["run_id"]
                try:
                    actual_channel = getattr(interaction, "channel", None)
                    actual_parent = getattr(actual_channel, "parent", None)
                    target = card.get("target") or {}
                    result = service.handle_interaction(
                        run_id,
                        custom_id=component.get("custom_id", ""),
                        actor_id=str(getattr(getattr(interaction, "user", None), "id", "") or ""),
                        origin_channel_id=str(getattr(actual_parent, "id", "") or target.get("channel_id") or ""),
                        origin_thread_id=str(getattr(actual_channel, "id", "") or ""),
                    )
                    await interaction.response.send_message(_interview_reply(result), ephemeral=True)
                    await _render_latest_card(interaction.channel, service, run_id)
                except Exception as exc:
                    await interaction.response.send_message(f"Minerva interaction rejected: {exc}", ephemeral=True)
            return _callback

    return MinervaView()


def _button_style(discord: Any, style: str) -> Any:
    return {
        "primary": discord.ButtonStyle.primary,
        "secondary": discord.ButtonStyle.secondary,
        "success": discord.ButtonStyle.success,
        "danger": discord.ButtonStyle.danger,
    }.get(style, discord.ButtonStyle.secondary)


async def _safe_send(adapter: Any, chat_id: str, content: str) -> None:
    if adapter is None or not chat_id:
        return
    try:
        await adapter.send(str(chat_id), content)
    except Exception:
        return
