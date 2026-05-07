"""Hermes plugin bridge for ZeusOS HOOO Discord UX.

Source-untouched integration: keep this in the ZeusOS repo and symlink/copy the
plugin directory into ~/.hermes/plugins only when the operator approves a gateway
restart. The plugin intercepts `/hooo ...` and `/houroboros ...` Discord text
commands, creates a sibling task thread, starts a ZeusOS HOOO run, renders the
latest `discord_cards.jsonl` record as Discord buttons, and reduces button
clicks through `HouroborosWorkflow.handle_interaction()`.
"""
from __future__ import annotations

import asyncio
import json
import re
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

_COMMAND_RE = re.compile(r"^/(?:hooo|houroboros)(?:\s+(?P<goal>.+))?$", re.I | re.S)
_MAX_THREAD_NAME = 80


@dataclass(frozen=True)
class HoooCommand:
    goal: str


def register(api: Any) -> None:
    api.register_hook("pre_gateway_dispatch", _pre_gateway_dispatch)


def parse_hooo_command(text: str) -> HoooCommand | None:
    match = _COMMAND_RE.match((text or "").strip())
    if not match:
        return None
    goal = (match.group("goal") or "").strip()
    if not goal:
        goal = "Discord-origin HOOO task"
    return HoooCommand(goal=goal)


def _redact_text(value: str) -> str:
    return _SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def _thread_name(goal: str) -> str:
    safe = re.sub(r"[\s\n\r\t]+", " ", _redact_text(goal)).strip()
    safe = re.sub(r"[`*_~<>@#:/\\]", "", safe)
    if not safe:
        safe = "HOOO task"
    name = f"HOOO · {safe}"
    return name[: _MAX_THREAD_NAME - 1] + "…" if len(name) > _MAX_THREAD_NAME else name


def _pre_gateway_dispatch(event: Any = None, gateway: Any = None, **_: Any) -> dict[str, Any] | None:
    command = parse_hooo_command(getattr(event, "text", ""))
    if not command:
        return None
    source = getattr(event, "source", None)
    if str(getattr(getattr(source, "platform", None), "value", getattr(source, "platform", ""))) != "discord":
        return None
    if gateway is not None and hasattr(gateway, "_is_user_authorized") and not gateway._is_user_authorized(source):
        return {"action": "skip", "reason": "unauthorized_hooo_command"}
    try:
        asyncio.get_running_loop().create_task(_handle_hooo_command(event, gateway, command))
    except RuntimeError:
        asyncio.run(_handle_hooo_command(event, gateway, command))
    return {"action": "skip", "reason": "hooo_gateway_bridge"}


async def _handle_hooo_command(event: Any, gateway: Any, command: HoooCommand) -> None:
    raw_message = getattr(event, "raw_message", None)
    source = getattr(event, "source", None)
    adapter = getattr(gateway, "adapters", {}).get(getattr(source, "platform", None)) if gateway is not None else None
    channel = getattr(raw_message, "channel", None)
    if channel is None:
        await _safe_send(adapter, getattr(source, "chat_id", ""), "HOOO: Discord channel을 확인하지 못했습니다.")
        return
    parent = getattr(channel, "parent", None) or channel
    if parent.__class__.__name__ == "DMChannel":
        await _safe_send(adapter, getattr(source, "chat_id", ""), "HOOO는 서버 텍스트 채널/스레드에서만 thread를 만들 수 있습니다.")
        return

    parent_id = str(getattr(parent, "id", getattr(source, "parent_chat_id", "") or getattr(source, "chat_id", "")))
    source_thread_id = str(getattr(source, "thread_id", "") or "")
    thread_name = _thread_name(command.goal)

    from zeus_os.config import load_pipeline_config
    from zeus_os.houroboros import HouroborosWorkflow

    service = HouroborosWorkflow.from_config(load_pipeline_config(DEFAULT_CONFIG))
    status = service.start(
        command.goal,
        origin_platform="discord",
        origin_channel_id=parent_id,
        origin_thread_id=source_thread_id,
        origin_message_id=str(getattr(raw_message, "id", "") or ""),
        auto_open_thread=True,
        thread_name=thread_name,
    )
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
    await _safe_send(adapter, getattr(source, "chat_id", parent_id), f"HOOO thread 생성: <#{thread_id}> (`{status['run_id']}`)")


async def _create_sibling_thread(parent: Any, raw_message: Any, name: str) -> Any:
    try:
        return await parent.create_thread(name=name, auto_archive_duration=1440, reason="HOOO task thread")
    except Exception:
        seed = await parent.send(f"🌀 HOOO task: **{name}**")
        return await seed.create_thread(name=name, auto_archive_duration=1440, reason="HOOO task thread fallback")


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
    lines = [f"🌀 **HOOO** `{run_id}`", f"phase: `{phase}`"]
    if proposal_card:
        lines.append(f"\n선택할 항목: **{proposal_card.get('label', proposal_card.get('dimension', 'HOOO'))}**")
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
        "scope": "Scope: 이번 HOOO가 다룰 범위와 제외 범위",
        "acceptance": "Acceptance: 완료로 인정할 산출물/검증 기준",
        "constraint": "Constraint: 건드리면 안 되는 파일·서비스·권한",
        "executor": "Executor: boramae / claude-code / opencode 등 실행 주체",
        "permission": "Permission: read-only, seed 승인, 구현 승인 여부",
    }.get(dimension, f"{dimension}: ...")


def _interview_reply(result: dict[str, Any]) -> str:
    interaction = result.get("interaction") or {}
    unresolved = interaction.get("next_unresolved") or result.get("interview_state", {}).get("unresolved") or []
    if not unresolved:
        return f"HOOO 처리됨: `{result['phase']}` — Seed 생성 가능 상태입니다."
    prompts = "\n".join(f"- `{_dimension_prompt(item)}`" for item in unresolved[:5])
    return f"HOOO 인터뷰 계속: `{result['phase']}`\n남은 항목:\n{prompts}"


async def _render_latest_card(thread: Any, service: Any, run_id: str) -> None:
    card = _latest_card(service, run_id)
    view = _build_view(service, card)
    await thread.send(_card_text(card), view=view)


def _build_view(service: Any, card: dict[str, Any]) -> Any:
    import discord

    class HoooView(discord.ui.View):
        def __init__(self) -> None:
            super().__init__(timeout=None)
            for component in _card_components(card):
                if component.get("type") != "button":
                    continue
                button = discord.ui.Button(
                    label=component.get("label", component.get("action", "HOOO")),
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
                    await interaction.response.send_message(f"HOOO interaction rejected: {exc}", ephemeral=True)
            return _callback

    return HoooView()


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
