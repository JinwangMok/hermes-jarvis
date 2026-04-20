from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig

MAX_SECTION_ITEMS = 5
NEW_IMPORTANT_LOOKBACK_DAYS = 14
CONTINUING_IMPORTANT_AGE_DAYS = 21
PAST_DUE_GRACE_HOURS = 12


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_open_proposals(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT ep.proposal_id, ep.source_message_id, ep.title, ep.start_ts, ep.end_ts,
               ep.location, ep.confidence, ep.status, ep.reason_json, ep.created_at,
               m.subject, m.from_addr, m.sent_at,
               mw.first_seen_at, mw.last_seen_at, mw.seen_count
        FROM event_proposals AS ep
        LEFT JOIN messages AS m ON m.message_id = ep.source_message_id
        LEFT JOIN message_watchlist AS mw ON mw.source_message_id = ep.source_message_id
        WHERE ep.status = 'proposed'
        ORDER BY ep.confidence DESC, COALESCE(ep.start_ts, m.sent_at, ep.created_at) ASC, ep.proposal_id ASC
        """
    ).fetchall()
    proposals: list[dict] = []
    for row in rows:
        item = dict(row)
        item["reason"] = json.loads(item["reason_json"]) if item.get("reason_json") else {}
        label_rows = conn.execute(
            "SELECT label FROM message_labels WHERE message_id = ? ORDER BY score DESC, label ASC",
            (item["source_message_id"],),
        ).fetchall()
        item["labels"] = [label for (label,) in label_rows]
        proposals.append(item)
    return proposals


def _load_backfill_status(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT window_name, window_start, window_end, status, messages_scanned
        FROM backfill_runs
        ORDER BY window_name ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _first_non_null(*values: object) -> object | None:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _format_when(value: str | None) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return "시간 미정"
    local = parsed.astimezone()
    return local.strftime("%Y-%m-%d %H:%M")


def _freshness_anchor(proposal: dict) -> datetime | None:
    anchor = _first_non_null(
        _parse_datetime(proposal.get("first_seen_at")),
        _parse_datetime(proposal.get("sent_at")),
        _parse_datetime(proposal.get("created_at")),
    )
    return anchor if isinstance(anchor, datetime) else None


def _localize_naive(value: datetime) -> datetime:
    return value.replace(tzinfo=datetime.now().astimezone().tzinfo)


def _infer_subject_deadline(proposal: dict, *, as_of: datetime) -> datetime | None:
    subject = (proposal.get("subject") or proposal.get("title") or "").strip()
    if not subject:
        return None

    local_as_of = as_of.astimezone()
    sent_at = _parse_datetime(proposal.get("sent_at"))
    base_local = (sent_at or local_as_of).astimezone()

    month = None
    day = None
    month_day_match = re.search(r"(?P<month>\d{1,2})\s*[./-]\s*(?P<day>\d{1,2})", subject)
    if month_day_match:
        month = int(month_day_match.group("month"))
        day = int(month_day_match.group("day"))
    else:
        day_only_match = re.search(r"(?<!\d)(?P<day>\d{1,2})일(?!\d)", subject)
        if day_only_match:
            month = base_local.month
            day = int(day_only_match.group("day"))

    if month is None or day is None:
        return None

    try:
        inferred = datetime(base_local.year, month, day)
    except ValueError:
        return None

    time_match = re.search(
        r"(?:(?P<ampm>오전|오후)\s*)?(?P<hour>\d{1,2})(?:[:시]\s*(?P<minute>\d{1,2}))?\s*(?:분)?\s*(?:까지|마감|제출)",
        subject,
    )
    if time_match:
        hour = int(time_match.group("hour"))
        minute = int(time_match.group("minute") or 0)
        ampm = time_match.group("ampm")
        if ampm == "오후" and hour < 12:
            hour += 12
        elif ampm == "오전" and hour == 12:
            hour = 0
        inferred = inferred.replace(hour=hour, minute=minute)
    else:
        inferred = inferred.replace(hour=23, minute=59)

    return _localize_naive(inferred).astimezone(UTC)


def _effective_due_datetime(proposal: dict, *, as_of: datetime) -> datetime | None:
    explicit_due = _parse_datetime(proposal.get("end_ts")) or _parse_datetime(proposal.get("start_ts"))
    if explicit_due is not None:
        return explicit_due
    return _infer_subject_deadline(proposal, as_of=as_of)


def _filter_actionable_proposals(proposals: list[dict], *, as_of: datetime) -> list[dict]:
    actionable: list[dict] = []
    for proposal in proposals:
        due_at = _effective_due_datetime(proposal, as_of=as_of)
        if due_at is not None and due_at + timedelta(hours=PAST_DUE_GRACE_HOURS) < as_of:
            continue
        actionable.append(proposal)
    return actionable


def _line_for_proposal(proposal: dict, *, include_schedule_hint: bool = False) -> str:
    subject = proposal.get("subject") or proposal.get("title") or "(제목 없음)"
    sender = proposal.get("from_addr") or "unknown"
    sent_at = _format_when(proposal.get("sent_at"))
    labels = ", ".join(proposal.get("labels") or []) or "라벨 없음"
    base = f"- {subject} — from {sender}, sent {sent_at}, confidence {float(proposal['confidence']):.2f}, labels: {labels}"
    if include_schedule_hint:
        if proposal.get("start_ts") and proposal.get("end_ts"):
            base += f" | 추천 일정: {_format_when(proposal['start_ts'])} ~ {_format_when(proposal['end_ts'])}"
        else:
            base += " | 추천 일정: 시간 정보 부족(바로 등록 불가)"
    return base


def _select_recent_important(proposals: list[dict], *, as_of: datetime) -> list[dict]:
    selected: list[dict] = []
    for proposal in proposals:
        freshness_anchor = _freshness_anchor(proposal)
        if freshness_anchor is None:
            continue
        if (as_of - freshness_anchor).days <= NEW_IMPORTANT_LOOKBACK_DAYS:
            selected.append(proposal)
    selected.sort(
        key=lambda proposal: (
            _freshness_anchor(proposal) or datetime.min.replace(tzinfo=UTC),
            float(proposal.get("confidence") or 0.0),
        ),
        reverse=True,
    )
    return selected[:MAX_SECTION_ITEMS]


def _select_continuing_important(proposals: list[dict], *, as_of: datetime) -> list[dict]:
    selected: list[dict] = []
    for proposal in proposals:
        sent_at = _parse_datetime(proposal.get("sent_at"))
        first_seen = _parse_datetime(proposal.get("first_seen_at"))
        age_anchor = first_seen or sent_at
        seen_count = int(proposal.get("seen_count") or 0)
        if seen_count >= 2:
            selected.append(proposal)
            continue
        if age_anchor is not None and (as_of - age_anchor).days >= CONTINUING_IMPORTANT_AGE_DAYS:
            selected.append(proposal)
    return selected[:MAX_SECTION_ITEMS]


def _select_newly_important(proposals: list[dict], *, as_of: datetime) -> list[dict]:
    selected: list[dict] = []
    for proposal in proposals:
        freshness_anchor = _freshness_anchor(proposal)
        if freshness_anchor is None:
            continue
        if (as_of - freshness_anchor).days <= NEW_IMPORTANT_LOOKBACK_DAYS:
            selected.append(proposal)
    selected.sort(
        key=lambda proposal: (
            _freshness_anchor(proposal) or datetime.min.replace(tzinfo=UTC),
            float(proposal.get("confidence") or 0.0),
        ),
        reverse=True,
    )
    return selected[:MAX_SECTION_ITEMS]


def _select_schedule_recommendations(proposals: list[dict]) -> list[dict]:
    with_time = [proposal for proposal in proposals if proposal.get("start_ts") and proposal.get("end_ts")]
    return with_time[:MAX_SECTION_ITEMS]


def _artifact_path(workspace_root: Path, moment: datetime) -> Path:
    artifact_dir = workspace_root / "data" / "briefings"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir / f"briefing-{moment.strftime('%Y%m%dT%H%M%SZ')}.json"


def _render_message_text(*, generated_at: datetime, target_channel: str, recent: list[dict], continuing: list[dict], new_items: list[dict], schedule_items: list[dict]) -> str:
    lines = [
        f"# Jarvis 브리핑 — {generated_at.astimezone().strftime('%Y-%m-%d %H:%M')}",
        f"보고 채널: {target_channel}",
        "",
        "지금 기준으로, 바로 챙겨볼 만한 메일/업무 흐름만 정리했어.",
        "",
        "## 최근 중요한 일",
    ]
    if recent:
        lines.extend(_line_for_proposal(item) for item in recent)
    else:
        lines.append("- 현재 열린 중요 항목이 없습니다.")

    lines.extend(["", "## 계속 중요한 일"])
    if continuing:
        lines.extend(_line_for_proposal(item) for item in continuing)
    else:
        lines.append("- 장기적으로 이어지는 열린 항목은 아직 두드러지지 않습니다.")

    lines.extend(["", "## 새로 중요해진 일"])
    if new_items:
        lines.extend(_line_for_proposal(item) for item in new_items)
    else:
        lines.append("- 이번 브리핑에서 새로 급부상한 항목은 아직 없습니다.")

    lines.extend(["", "## 추천 일정"])
    if schedule_items:
        lines.extend(_line_for_proposal(item, include_schedule_hint=True) for item in schedule_items)
    else:
        lines.append("- 현재 바로 캘린더에 넣을 수 있을 만큼 시간 정보가 갖춰진 추천 일정은 없습니다.")

    lines.extend([
        "",
        "## 확인 요청",
        "캘린더에 등록할까요?",
    ])
    if schedule_items:
        for item in schedule_items:
            lines.append(
                f"- 허용 후보: {item['title']} → allow 시 캘린더 생성 가능"
            )
    else:
        lines.append("- 아직 시간 정보가 충분한 일정 후보가 없어 승인 요청은 보류합니다.")
    return "\n".join(lines) + "\n"


def generate_briefing(config: PipelineConfig, *, as_of: datetime | None = None) -> dict:
    bootstrap_workspace(config)
    moment = (as_of or _utc_now()).astimezone(UTC).replace(microsecond=0)
    with sqlite3.connect(config.database_path) as conn:
        proposals = _load_open_proposals(conn)
        backfill_runs = _load_backfill_status(conn)

    actionable_proposals = _filter_actionable_proposals(proposals, as_of=moment)
    recent = _select_recent_important(actionable_proposals, as_of=moment)
    continuing = _select_continuing_important(actionable_proposals, as_of=moment)
    new_items = _select_newly_important(actionable_proposals, as_of=moment)
    schedule_items = _select_schedule_recommendations(actionable_proposals)
    message_text = _render_message_text(
        generated_at=moment,
        target_channel=config.deliver_channel,
        recent=recent,
        continuing=continuing,
        new_items=new_items,
        schedule_items=schedule_items,
    )
    artifact = {
        "generated_at": moment.isoformat(),
        "target_channel": config.deliver_channel,
        "pending_approval_count": len(schedule_items),
        "open_proposal_count": len(actionable_proposals),
        "backfill_runs": backfill_runs,
        "sections": {
            "recent_important": recent,
            "continuing_important": continuing,
            "newly_important": new_items,
            "schedule_recommendations": schedule_items,
        },
        "message_text": message_text,
    }
    artifact_path = _artifact_path(config.workspace_root, moment)
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    checkpoints = {}
    if config.checkpoints_path.exists():
        checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8"))
    checkpoints.setdefault("briefing", {})
    checkpoints["briefing"]["latest"] = {
        "generated_at": moment.isoformat(),
        "artifact_file": artifact_path.name,
        "open_proposal_count": len(actionable_proposals),
        "pending_approval_count": len(schedule_items),
        "target_channel": config.deliver_channel,
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "generated_at": moment.isoformat(),
        "artifact_path": artifact_path,
        "target_channel": config.deliver_channel,
        "open_proposal_count": len(actionable_proposals),
        "pending_approval_count": len(schedule_items),
        "message_text": message_text,
    }
