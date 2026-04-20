from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from .bootstrap import bootstrap_workspace
from .calendar import build_dedup_key
from .config import PipelineConfig

ACTION_SIGNAL_REPLY_DETECTED = "reply_detected"
ACTION_SIGNAL_HISTORICALLY_ACTIONED = "historically_actioned"
PROPOSAL_STATUS_PROPOSED = "proposed"
DEFAULT_TIMEZONE = "+09:00"

DATE_PATTERNS = (
    re.compile(
        r"(?P<year>20\d{2})[./-](?P<month>\d{1,2})[./-](?P<day>\d{1,2})(?:\s*(?:\(|\[)?(?P<weekday>월|화|수|목|금|토|일)(?:요일)?(?:\)|\])?)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<year2>\d{2})[./-](?P<month>\d{1,2})[./-](?P<day>\d{1,2})(?:\s*(?:\(|\[)?(?P<weekday>월|화|수|목|금|토|일)(?:요일)?(?:\)|\])?)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<month>\d{1,2})[./-](?P<day>\d{1,2})(?:\s*(?:\(|\[)?(?P<weekday>월|화|수|목|금|토|일)(?:요일)?(?:\)|\])?)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<month_name>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<year>20\d{2}))?",
        re.IGNORECASE,
    ),
)
TIME_PATTERNS = (
    re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?", re.IGNORECASE),
    re.compile(r"(?P<ampm>오전|오후)\s*(?P<hour>\d{1,2})(?:[:시]\s*(?P<minute>\d{1,2}))?\s*분?", re.IGNORECASE),
    re.compile(r"(?P<hour>\d{1,2})\s*시(?:\s*(?P<minute>\d{1,2})\s*분?)?", re.IGNORECASE),
)
TIME_RANGE_PATTERNS = (
    re.compile(
        r"(?P<start_hour>\d{1,2}):(?P<start_minute>\d{2})\s*(?P<start_ampm>am|pm)?\s*(?:-|~|to)\s*(?P<end_hour>\d{1,2}):(?P<end_minute>\d{2})\s*(?P<end_ampm>am|pm)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<start_ampm>오전|오후)?\s*(?P<start_hour>\d{1,2})\s*시(?:\s*(?P<start_minute>\d{1,2})\s*분?)?\s*(?:-|~)\s*(?P<end_ampm>오전|오후)?\s*(?P<end_hour>\d{1,2})\s*시(?:\s*(?P<end_minute>\d{1,2})\s*분?)?",
        re.IGNORECASE,
    ),
)
MONTH_NAME_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
TASK_HINTS = (
    "review",
    "reply",
    "prepare",
    "prep",
    "submit",
    "confirm",
    "deadline",
    "action required",
    "요청",
    "준비",
    "검토",
    "회신",
    "제출",
)
MEETING_HINTS = (
    "meeting",
    "seminar",
    "agenda",
    "zoom",
    "call",
    "미팅",
    "회의",
    "세미나",
)
NOISE_HINTS = (
    "newsletter",
    "promo",
    "vendor",
    "sale",
    "광고",
    "security alert",
)
PROMO_SUPPRESSION_HINTS = (
    "join ",
    "speaker",
    "speak at",
    "summit",
    "kubecon",
    "cloudnativecon",
    "사업설명회",
    "초대",
    "초대장",
    "trend",
    "it trend",
    "announce",
    "alert:",
    "reminder:",
    "spoofing",
    "인사이트",
    "소개자료",
    "공유드립니다",
    "자료 공유",
)
EXTERNAL_SEMINAR_HINTS = (
    "seminar",
    "webinar",
    "온라인",
    "zoom",
    "동향",
)
REPORT_THREAD_HINTS = (
    "보고",
    "보고드립니다",
    "진행 현황",
    "현황",
    "업데이트",
    "update",
)
FORWARDED_ADMIN_HINTS = (
    "사전등록",
    "조사 요청",
    "준비위원회",
)


@dataclass(frozen=True)
class MessageContext:
    message_id: str
    account: str
    folder_kind: str
    subject: str
    from_addr: str | None
    sent_at: str | None
    role: str
    priority_base: int
    labels: tuple[dict, ...]


@dataclass(frozen=True)
class CandidateEvent:
    title: str
    start_ts: str | None
    end_ts: str | None
    dedup_key: str
    date_confidence: float
    parse_reason: dict


def _normalize_subject(subject: str | None) -> str:
    value = (subject or "").strip().casefold()
    value = re.sub(r"^(re|fw|fwd)\s*:\s*", "", value)
    value = re.sub(r"\[[^\]]+\]\s*", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _compact_subject(subject: str | None) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", _normalize_subject(subject))


def _clean_title(subject: str | None) -> str:
    cleaned = re.sub(r"^(re|fw|fwd)\s*:\s*", "", (subject or "").strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -[]")
    return cleaned or "Untitled proposal"


def _parse_json(value: str | None) -> dict:
    if not value:
        return {}
    return json.loads(value)


def _load_messages(database_path: Path) -> list[MessageContext]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                m.message_id,
                m.account,
                m.folder_kind,
                m.subject,
                m.from_addr,
                m.sent_at,
                COALESCE(si.role, 'external') AS role,
                COALESCE(si.priority_base, 0) AS priority_base
            FROM messages AS m
            LEFT JOIN sender_identities AS si ON LOWER(si.email) = LOWER(m.from_addr)
            ORDER BY m.sent_at IS NULL, m.sent_at, m.message_id
            """
        ).fetchall()
        label_rows = conn.execute(
            "SELECT message_id, label, score, reason_json FROM message_labels ORDER BY message_id, score DESC, label"
        ).fetchall()
    labels_by_message: dict[str, list[dict]] = {}
    for row in label_rows:
        labels_by_message.setdefault(row["message_id"], []).append(
            {
                "label": row["label"],
                "score": float(row["score"]),
                "reason": _parse_json(row["reason_json"]),
            }
        )
    return [
        MessageContext(
            message_id=row["message_id"],
            account=row["account"],
            folder_kind=row["folder_kind"],
            subject=row["subject"] or "",
            from_addr=row["from_addr"],
            sent_at=row["sent_at"],
            role=row["role"],
            priority_base=int(row["priority_base"]),
            labels=tuple(labels_by_message.get(row["message_id"], [])),
        )
        for row in rows
    ]


def _load_calendar_rows(database_path: Path) -> list[dict]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT event_id, summary, start_ts, dedup_key FROM calendar_events WHERE COALESCE(status, 'confirmed') != 'cancelled'"
        ).fetchall()
    return [dict(row) for row in rows]


def _load_feedback_suppressions(database_path: Path) -> list[dict]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT ep.proposal_id, ep.source_message_id, ep.title, ep.start_ts, ep.dedup_key, pf.decision, pf.reason_code
            FROM proposal_feedback AS pf
            JOIN event_proposals AS ep ON ep.proposal_id = pf.proposal_id
            WHERE pf.decision = 'reject'
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _load_watchlist_rows(database_path: Path) -> dict[str, dict]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT source_message_id, watch_kind, promotion_score, first_seen_at, last_seen_at, seen_count, latest_reason_json
            FROM message_watchlist
            """
        ).fetchall()
    payload: dict[str, dict] = {}
    for row in rows:
        data = dict(row)
        if data.get("latest_reason_json"):
            data["latest_reason"] = json.loads(data["latest_reason_json"])
        payload[str(data["source_message_id"])] = data
    return payload


def _load_existing_proposals(database_path: Path) -> list[dict]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT proposal_id, title, start_ts, dedup_key, status
            FROM event_proposals
            WHERE status IN ('proposed', 'allowed', 'expired')
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _role_bonus(role: str) -> float:
    return {
        "advisor": 0.35,
        "self": 0.2,
        "research-professor": 0.18,
        "phd-student": 0.08,
        "ms-student": 0.06,
        "lab-member": 0.05,
        "external": 0.0,
    }.get(role, 0.0)


def _label_bonus(label: str) -> tuple[float, float, float, float]:
    mapping = {
        "advisor-request": (0.35, 0.35, 0.1, -0.1),
        "advisor-fyi": (0.12, 0.02, 0.02, 0.08),
        "meeting": (0.1, 0.1, 0.35, -0.05),
        "lab": (0.08, 0.05, 0.05, -0.02),
        "ta": (0.05, 0.05, 0.08, -0.02),
        "work-account": (0.05, 0.02, 0.03, 0.0),
        "promotional-reference": (-0.05, -0.05, -0.1, 0.2),
        "security-routine": (-0.1, -0.2, -0.15, 0.3),
    }
    return mapping.get(label, (0.0, 0.0, 0.0, 0.0))


def derive_message_scores(message: MessageContext) -> dict:
    subject_lower = message.subject.casefold()
    priority = 0.1 + min(message.priority_base / 200.0, 0.45) + _role_bonus(message.role)
    action = 0.05 + _role_bonus(message.role) * 0.7
    calendar_conf = 0.05
    noise = 0.05
    reasons = {
        "role": message.role,
        "priority_base": message.priority_base,
        "labels": [],
        "subject_hints": [],
        "account": message.account,
        "folder_kind": message.folder_kind,
    }

    if message.folder_kind == "inbox":
        priority += 0.08
        action += 0.06
        reasons["subject_hints"].append("inbox-message")
    elif message.folder_kind == "sent":
        action -= 0.2
        calendar_conf -= 0.05
        reasons["subject_hints"].append("sent-message")

    if message.account == "smartx":
        priority += 0.06
        action += 0.03
        reasons["subject_hints"].append("work-account")

    for label in message.labels:
        p_bonus, a_bonus, c_bonus, n_bonus = _label_bonus(label["label"])
        priority += p_bonus
        action += a_bonus
        calendar_conf += c_bonus
        noise += n_bonus
        reasons["labels"].append({"label": label["label"], "score": label["score"]})

    for hint in TASK_HINTS:
        if hint in subject_lower:
            action += 0.12
            priority += 0.05
            noise -= 0.03
            reasons["subject_hints"].append(f"task:{hint}")
    for hint in MEETING_HINTS:
        if hint in subject_lower:
            calendar_conf += 0.15
            action += 0.04
            reasons["subject_hints"].append(f"meeting:{hint}")
    for hint in NOISE_HINTS:
        if hint in subject_lower:
            noise += 0.18
            priority -= 0.06
            action -= 0.08
            reasons["subject_hints"].append(f"noise:{hint}")

    if re.search(r"\b(please|kindly|urgent|asap)\b", subject_lower):
        action += 0.1
        priority += 0.07
        reasons["subject_hints"].append("request-language")
    if re.search(r"\b\d{1,2}[:.]\d{2}\b", subject_lower) or any(pattern.search(subject_lower) for pattern in DATE_PATTERNS):
        calendar_conf += 0.18
        reasons["subject_hints"].append("explicit-date-or-time")

    return {
        "priority": max(0.0, min(priority, 1.0)),
        "action": max(0.0, min(action, 1.0)),
        "calendar": max(0.0, min(calendar_conf, 1.0)),
        "noise": max(0.0, min(noise, 1.0)),
        "reasons": reasons,
    }


def _build_reply_signals(messages: list[MessageContext]) -> list[dict]:
    sent_messages = [message for message in messages if message.folder_kind == "sent"]
    inbox_messages = [message for message in messages if message.folder_kind == "inbox"]
    sent_by_subject: dict[str, list[MessageContext]] = {}
    for sent in sent_messages:
        key = _normalize_subject(sent.subject)
        if key:
            sent_by_subject.setdefault(key, []).append(sent)

    signals: list[dict] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for inbox in inbox_messages:
        key = _normalize_subject(inbox.subject)
        if not key:
            continue
        matches = sent_by_subject.get(key, [])
        if not matches:
            continue
        matches = sorted(matches, key=lambda item: (item.sent_at or "", item.message_id))
        newest = matches[-1]
        strongest_type = ACTION_SIGNAL_REPLY_DETECTED
        strongest_score = 0.95 if newest.account == inbox.account else 0.8
        for sent in matches:
            signal_type = ACTION_SIGNAL_REPLY_DETECTED if sent.account == inbox.account else ACTION_SIGNAL_HISTORICALLY_ACTIONED
            score = 0.95 if signal_type == ACTION_SIGNAL_REPLY_DETECTED else 0.78
            pair = (inbox.message_id, sent.message_id, signal_type)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            signals.append(
                {
                    "source_message_id": inbox.message_id,
                    "signal_type": signal_type,
                    "evidence_message_id": sent.message_id,
                    "score": score,
                }
            )
            if score > strongest_score:
                strongest_score = score
                strongest_type = signal_type
        if len(matches) > 1:
            pair = (inbox.message_id, newest.message_id, strongest_type)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                signals.append(
                    {
                        "source_message_id": inbox.message_id,
                        "signal_type": strongest_type,
                        "evidence_message_id": newest.message_id,
                        "score": strongest_score,
                    }
                )
    return signals


def _extract_date(subject: str) -> tuple[datetime | None, dict]:
    now = datetime.now(UTC).astimezone()
    reason: dict = {"matched_date": None, "matched_time": None}
    date_value: datetime | None = None
    lowered = subject.casefold()
    for pattern in DATE_PATTERNS:
        match = pattern.search(subject)
        if not match:
            continue
        groups = match.groupdict()
        if groups.get("year"):
            year = int(groups["year"])
        elif groups.get("year2"):
            year = 2000 + int(groups["year2"])
        else:
            year = now.year
        day = int(groups["day"])
        if groups.get("month_name"):
            month = MONTH_NAME_MAP[groups["month_name"][:3].casefold()]
        else:
            month = int(groups["month"])
            if not groups.get("year") and not groups.get("year2") and month < now.month - 6:
                year += 1
        try:
            date_value = datetime(year, month, day)
        except ValueError:
            continue
        reason["matched_date"] = match.group(0)
        break

    if date_value is None and ("tomorrow" in lowered or "내일" in lowered):
        next_day = now + timedelta(days=1)
        date_value = datetime(next_day.year, next_day.month, next_day.day)
        reason["matched_date"] = "relative:tomorrow"
    elif date_value is None and ("today" in lowered or "오늘" in lowered):
        date_value = datetime(now.year, now.month, now.day)
        reason["matched_date"] = "relative:today"

    if date_value is None:
        return None, reason

    for pattern in TIME_RANGE_PATTERNS:
        match = pattern.search(subject)
        if not match:
            continue
        groups = match.groupdict()
        start_hour, start_minute = _normalize_hour_minute(groups, prefix="start_")
        end_hour, end_minute = _normalize_hour_minute(groups, prefix="end_")
        reason["matched_time"] = match.group(0)
        start = date_value.replace(hour=start_hour, minute=start_minute)
        end = date_value.replace(hour=end_hour, minute=end_minute)
        return start, {**reason, "end": end.isoformat() + DEFAULT_TIMEZONE}

    for pattern in TIME_PATTERNS:
        match = pattern.search(subject)
        if not match:
            continue
        hour, minute = _normalize_hour_minute(match.groupdict())
        reason["matched_time"] = match.group(0)
        start = date_value.replace(hour=hour, minute=minute)
        return start, reason

    return date_value.replace(hour=9, minute=0), reason


def _normalize_hour_minute(groups: dict[str, str | None], prefix: str = "") -> tuple[int, int]:
    hour = int(groups[f"{prefix}hour"])
    minute = int(groups.get(f"{prefix}minute") or 0)
    ampm = (groups.get(f"{prefix}ampm") or "").casefold()
    if ampm in {"pm", "오후"} and hour < 12:
        hour += 12
    if ampm in {"am", "오전"} and hour == 12:
        hour = 0
    return hour, minute


def extract_candidate_event(message: MessageContext, scores: dict) -> CandidateEvent | None:
    subject = message.subject.strip()
    if not subject or message.folder_kind != "inbox":
        return None

    label_names = {label["label"] for label in message.labels}
    subject_lower = subject.casefold()
    start_dt, parse_reason = _extract_date(subject)
    title = _clean_title(subject)
    date_confidence = 0.0
    start_ts = None
    end_ts = None

    if start_dt is not None:
        start_ts = start_dt.isoformat() + DEFAULT_TIMEZONE
        end_ts = parse_reason.get("end")
        if end_ts is None:
            end_ts = (start_dt + timedelta(hours=1)).isoformat() + DEFAULT_TIMEZONE
        date_confidence = 0.78 if parse_reason.get("matched_time") else 0.62
    elif (
        scores["action"] >= 0.62
        and scores["priority"] >= 0.55
        and scores["noise"] <= 0.38
        and ("advisor-request" in label_names or "meeting" in label_names or any(hint in subject_lower for hint in TASK_HINTS))
    ):
        date_confidence = 0.22
    else:
        return None

    dedup_key = build_dedup_key(title, start_ts)
    return CandidateEvent(
        title=title,
        start_ts=start_ts,
        end_ts=end_ts,
        dedup_key=dedup_key,
        date_confidence=date_confidence,
        parse_reason=parse_reason,
    )


def _similar_summary(a: str, b: str) -> float:
    return SequenceMatcher(a=_compact_subject(a), b=_compact_subject(b)).ratio()


def _suppression_reason(candidate: CandidateEvent, calendar_rows: list[dict], feedback_rows: list[dict]) -> dict | None:
    for row in calendar_rows:
        if row["dedup_key"] == candidate.dedup_key:
            return {"kind": "calendar-dedup-key", "event_id": row["event_id"], "summary": row.get("summary")}
        if candidate.start_ts and row.get("start_ts") == candidate.start_ts and _similar_summary(candidate.title, row.get("summary") or "") >= 0.84:
            return {"kind": "calendar-summary-match", "event_id": row["event_id"], "summary": row.get("summary")}
    for row in feedback_rows:
        if row.get("dedup_key") == candidate.dedup_key:
            return {"kind": "feedback-dedup-key", "proposal_id": row["proposal_id"], "reason_code": row["reason_code"]}
        if _similar_summary(candidate.title, row.get("title") or "") >= 0.9 and (not row.get("start_ts") or row.get("start_ts") == candidate.start_ts):
            return {"kind": "feedback-summary-match", "proposal_id": row["proposal_id"], "reason_code": row["reason_code"]}
    return None


def _build_proposal_record(
    message: MessageContext,
    scores: dict,
    candidate: CandidateEvent,
    suppression: dict | None,
    signal_confidence: float,
    watch_row: dict | None = None,
    as_of: datetime | None = None,
) -> tuple[dict | None, dict]:
    label_names = {label["label"] for label in message.labels}
    subject_lower = message.subject.casefold()
    confidence = (
        scores["priority"] * 0.3
        + scores["action"] * 0.25
        + scores["calendar"] * 0.25
        + candidate.date_confidence * 0.2
        - scores["noise"] * 0.25
        + signal_confidence * 0.05
    )
    if message.role == "external" and any(hint in subject_lower for hint in EXTERNAL_SEMINAR_HINTS) and "advisor-request" not in label_names:
        confidence -= 0.12
    if candidate.start_ts is None and signal_confidence >= 0.9 and any(hint in subject_lower for hint in REPORT_THREAD_HINTS):
        confidence -= 0.22
    if subject_lower.startswith(("fw:", "fwd:")) and any(hint in subject_lower for hint in FORWARDED_ADMIN_HINTS):
        confidence -= 0.12
    watch_info = None
    if watch_row is not None:
        reference = as_of or datetime.now(UTC)
        reference = reference.astimezone(UTC) if reference.tzinfo else reference.replace(tzinfo=UTC)
        watch_boost = 0.0
        seen_count = int(watch_row.get("seen_count") or 0)
        promotional_subject = any(hint in subject_lower for hint in PROMO_SUPPRESSION_HINTS)
        if seen_count >= 2:
            watch_boost += 0.08
        if seen_count >= 3:
            watch_boost += 0.04
        if watch_row.get("watch_kind") == "reply-backed-candidate" and signal_confidence >= 0.9:
            watch_boost += 0.12
        if candidate.start_ts:
            start_dt = datetime.fromisoformat(candidate.start_ts)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=UTC)
            days_until = (start_dt.astimezone(UTC) - reference).total_seconds() / 86400.0
            if 0.0 <= days_until <= 14.0:
                watch_boost += 0.10
        if watch_row.get("watch_kind") == "advisor-fyi-revival" and "advisor-fyi" in label_names:
            watch_boost += 0.06
        if promotional_subject and signal_confidence < 0.9:
            watch_boost = 0.0
        confidence += watch_boost
        watch_info = {
            "resurrected": watch_boost >= 0.12,
            "watch_kind": watch_row.get("watch_kind"),
            "seen_count": seen_count,
            "promotion_score": float(watch_row.get("promotion_score") or 0.0),
            "boost": round(watch_boost, 4),
        }
    confidence = max(0.0, min(confidence, 1.0))
    policy_suppression = None
    if "security-routine" in label_names:
        policy_suppression = {"kind": "policy-security-routine"}
    elif (
        "promotional-reference" in label_names
        and "advisor-request" not in label_names
        and "meeting" not in label_names
        and candidate.start_ts is None
    ):
        policy_suppression = {"kind": "policy-promotional-dateless"}
    elif (
        any(hint in subject_lower for hint in PROMO_SUPPRESSION_HINTS)
        and signal_confidence < 0.9
        and confidence < 0.88
        and (
            "advisor-request" not in label_names
            or candidate.start_ts is None
            or "meeting" not in label_names
        )
    ):
        policy_suppression = {"kind": "policy-promotional-subject"}
    elif (
        any(hint in subject_lower for hint in EXTERNAL_SEMINAR_HINTS)
        and message.role == "external"
        and signal_confidence < 0.9
        and confidence < 0.55
    ):
        policy_suppression = {"kind": "policy-external-seminar-low-confidence"}
    elif "advisor-fyi" in label_names:
        if candidate.start_ts is None:
            policy_suppression = {"kind": "policy-advisor-fyi-dateless"}
        elif confidence < 0.72:
            policy_suppression = {"kind": "policy-advisor-fyi-low-confidence"}
    elif candidate.start_ts is None and signal_confidence < 0.9 and "advisor-request" not in label_names and confidence < 0.68:
        policy_suppression = {"kind": "policy-low-confidence-dateless"}

    reason_json = {
        "scores": {
            "priority": scores["priority"],
            "action": scores["action"],
            "calendar": scores["calendar"],
            "noise": scores["noise"],
            "date_confidence": candidate.date_confidence,
            "signal_confidence": signal_confidence,
        },
        "message": {
            "account": message.account,
            "folder_kind": message.folder_kind,
            "role": message.role,
            "from_addr": message.from_addr,
        },
        "labels": [label["label"] for label in message.labels],
        "subject_hints": scores["reasons"]["subject_hints"],
        "parse": candidate.parse_reason,
        "watchlist": watch_info,
        "suppression": suppression or policy_suppression,
    }
    if watch_info and watch_info.get("resurrected") and policy_suppression and policy_suppression.get("kind") in {
        "policy-advisor-fyi-dateless",
        "policy-advisor-fyi-low-confidence",
        "policy-low-confidence-dateless",
    }:
        policy_suppression = None
        reason_json["suppression"] = suppression
    if suppression or policy_suppression or confidence < 0.42:
        return None, reason_json

    proposal_id = hashlib.sha256(
        f"{message.message_id}|{candidate.dedup_key}|{candidate.title}|{candidate.start_ts or ''}".encode("utf-8")
    ).hexdigest()[:24]
    return {
        "proposal_id": proposal_id,
        "source_message_id": message.message_id,
        "title": candidate.title,
        "start_ts": candidate.start_ts,
        "end_ts": candidate.end_ts,
        "location": None,
        "description_md": f"Source subject: {message.subject}",
        "confidence": confidence,
        "status": PROPOSAL_STATUS_PROPOSED,
        "dedup_key": candidate.dedup_key,
        "reason_json": json.dumps(reason_json, ensure_ascii=False),
    }, reason_json


def _replace_action_signals(database_path: Path, signals: list[dict], created_at: str) -> None:
    with sqlite3.connect(database_path) as conn:
        conn.execute("DELETE FROM action_signals")
        for signal in signals:
            conn.execute(
                """
                INSERT INTO action_signals (source_message_id, signal_type, evidence_message_id, score, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    signal["source_message_id"],
                    signal["signal_type"],
                    signal["evidence_message_id"],
                    signal["score"],
                    created_at,
                ),
            )
        conn.commit()


def _proposal_group_key(proposal: dict) -> str:
    if proposal.get("dedup_key"):
        return str(proposal["dedup_key"])
    return build_dedup_key(proposal.get("title"), proposal.get("start_ts"))


def _consolidate_proposals(proposals: list[dict]) -> tuple[list[dict], list[dict]]:
    selected: dict[str, dict] = {}
    suppressed: list[dict] = []
    for proposal in proposals:
        group_key = _proposal_group_key(proposal)
        existing = selected.get(group_key)
        if existing is None or float(proposal["confidence"]) > float(existing["confidence"]):
            if existing is not None:
                suppressed.append(
                    {
                        "source_message_id": existing["source_message_id"],
                        "title": existing["title"],
                        "dedup_key": existing["dedup_key"],
                        "reason": {"kind": "duplicate-proposal-group", "kept_proposal_id": proposal["proposal_id"]},
                    }
                )
            selected[group_key] = proposal
        else:
            suppressed.append(
                {
                    "source_message_id": proposal["source_message_id"],
                    "title": proposal["title"],
                    "dedup_key": proposal["dedup_key"],
                    "reason": {"kind": "duplicate-proposal-group", "kept_proposal_id": existing["proposal_id"]},
                }
            )
    return list(selected.values()), suppressed


def _expire_stale_proposals(database_path: Path, active_proposal_ids: list[str], resolved_at: str) -> None:
    with sqlite3.connect(database_path) as conn:
        if active_proposal_ids:
            placeholders = ", ".join("?" for _ in active_proposal_ids)
            conn.execute(
                f"""
                UPDATE event_proposals
                SET status = 'expired', resolved_at = ?
                WHERE status = 'proposed' AND proposal_id NOT IN ({placeholders})
                """,
                (resolved_at, *active_proposal_ids),
            )
        else:
            conn.execute(
                """
                UPDATE event_proposals
                SET status = 'expired', resolved_at = ?
                WHERE status = 'proposed'
                """,
                (resolved_at,),
            )
        conn.commit()


def _upsert_proposals(database_path: Path, proposals: list[dict], created_at: str) -> None:
    with sqlite3.connect(database_path) as conn:
        for proposal in proposals:
            conn.execute(
                """
                INSERT INTO event_proposals (
                    proposal_id, source_message_id, title, start_ts, end_ts, location,
                    description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    source_message_id = excluded.source_message_id,
                    title = excluded.title,
                    start_ts = excluded.start_ts,
                    end_ts = excluded.end_ts,
                    location = excluded.location,
                    description_md = excluded.description_md,
                    confidence = excluded.confidence,
                    dedup_key = excluded.dedup_key,
                    reason_json = excluded.reason_json,
                    created_at = excluded.created_at,
                    status = CASE
                        WHEN event_proposals.status IN ('allowed', 'rejected', 'expired') THEN event_proposals.status
                        ELSE excluded.status
                    END,
                    resolved_at = CASE
                        WHEN event_proposals.status IN ('allowed', 'rejected', 'expired') THEN event_proposals.resolved_at
                        ELSE event_proposals.resolved_at
                    END
                """,
                (
                    proposal["proposal_id"],
                    proposal["source_message_id"],
                    proposal["title"],
                    proposal["start_ts"],
                    proposal["end_ts"],
                    proposal["location"],
                    proposal["description_md"],
                    proposal["confidence"],
                    proposal["status"],
                    proposal["dedup_key"],
                    proposal["reason_json"],
                    created_at,
                ),
            )
        conn.commit()


def _update_checkpoints(config: PipelineConfig, generated_at: str, artifact_path: Path, proposal_count: int, action_signal_count: int, suppressed_count: int) -> None:
    checkpoints = {}
    if config.checkpoints_path.exists():
        checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8"))
    checkpoints.setdefault("proposals", {})
    checkpoints["proposals"]["latest"] = {
        "generated_at": generated_at,
        "artifact_file": artifact_path.name,
        "proposal_count": proposal_count,
        "action_signal_count": action_signal_count,
        "suppressed_count": suppressed_count,
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_artifact(workspace_root: Path, payload: dict, generated_at: str) -> Path:
    proposal_dir = workspace_root / "data" / "proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")
    artifact_path = proposal_dir / f"proposal-run-{timestamp}.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact_path


def generate_proposals(config: PipelineConfig, *, as_of: datetime | None = None) -> dict:
    bootstrap_workspace(config)
    messages = _load_messages(config.database_path)
    calendar_rows = _load_calendar_rows(config.database_path)
    feedback_rows = _load_feedback_suppressions(config.database_path)
    watchlist_rows = _load_watchlist_rows(config.database_path)
    generated_at = (as_of or datetime.now(UTC)).isoformat().replace("+00:00", "Z")

    scores_by_message = {message.message_id: derive_message_scores(message) for message in messages}
    action_signals = _build_reply_signals(messages)
    signal_score_by_message: dict[str, float] = {}
    for signal in action_signals:
        signal_score_by_message[signal["source_message_id"]] = max(
            signal_score_by_message.get(signal["source_message_id"], 0.0),
            float(signal["score"]),
        )

    raw_proposals: list[dict] = []
    suppressed: list[dict] = []
    for message in messages:
        scores = scores_by_message[message.message_id]
        candidate = extract_candidate_event(message, scores)
        if candidate is None:
            continue
        suppression = _suppression_reason(candidate, calendar_rows, feedback_rows)
        proposal, reason_json = _build_proposal_record(
            message,
            scores,
            candidate,
            suppression,
            signal_score_by_message.get(message.message_id, 0.0),
            watchlist_rows.get(message.message_id),
            as_of=as_of,
        )
        if proposal is None:
            suppressed.append(
                {
                    "source_message_id": message.message_id,
                    "title": candidate.title,
                    "dedup_key": candidate.dedup_key,
                    "reason": suppression or {"kind": "low-confidence", "confidence": reason_json["scores"]},
                    "details": reason_json,
                }
            )
            continue
        raw_proposals.append(proposal)

    proposals, duplicate_suppressed = _consolidate_proposals(raw_proposals)
    suppressed.extend(duplicate_suppressed)

    _replace_action_signals(config.database_path, action_signals, generated_at)
    _upsert_proposals(config.database_path, proposals, generated_at)
    _expire_stale_proposals(config.database_path, [proposal["proposal_id"] for proposal in proposals], generated_at)
    artifact_payload = {
        "generated_at": generated_at,
        "message_count": len(messages),
        "action_signal_count": len(action_signals),
        "proposal_count": len(proposals),
        "suppressed_count": len(suppressed),
        "action_signals": action_signals,
        "proposals": [
            {
                **{key: value for key, value in proposal.items() if key != "reason_json"},
                "reason": json.loads(proposal["reason_json"]),
            }
            for proposal in proposals
        ],
        "suppressed": suppressed,
    }
    artifact_path = _write_artifact(config.workspace_root, artifact_payload, generated_at)
    _update_checkpoints(config, generated_at, artifact_path, len(proposals), len(action_signals), len(suppressed))
    return {
        "generated_at": generated_at,
        "artifact_path": artifact_path,
        "message_count": len(messages),
        "action_signal_count": len(action_signals),
        "proposal_count": len(proposals),
        "suppressed_count": len(suppressed),
    }
