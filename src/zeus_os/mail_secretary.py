from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import PipelineConfig

# Confidence is deliberately heuristic, not a probability: body-backed analysis starts
# higher than subject/snippet-only analysis, and advisor-labelled mail receives a
# small boost because Jinwang treats it as operationally important. Priority weights
# similarly favor explicit action terms, advisor context, and task/calendar signals.
ACTION_TERMS = (
    "회신", "답장", "확인", "검토", "제출", "등록", "신청", "참석", "요청", "전달", "공유",
    "reply", "respond", "review", "submit", "register", "apply", "attend", "request", "confirm",
)
CALENDAR_TERMS = ("회의", "미팅", "세미나", "워크숍", "일정", "참석", "meeting", "seminar", "workshop", "schedule")
TASK_TERMS = ("마감", "까지", "due", "deadline", "todo", "action item", "제출", "신청", "등록")
RISK_TERMS = ("비밀번호", "password", "계좌", "송금", "계약", "법무", "secret", "token", "api key", "견적", "구매")
NOISE_TERMS = ("newsletter", "광고", "프로모션", "보안 알림", "security alert", "receipt")
SECRET_REDACTION_PATTERNS = (
    re.compile(r"(?i)\b(api\s*key|password|passwd|pwd|token|secret)\b\s*[:=]\s*[^\s,;\]\[)}{]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9._-]{10,}"),
)


def _redact_secrets(text: str | None) -> str:
    redacted = text or ""
    for pattern in SECRET_REDACTION_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]" if match.lastindex else "[REDACTED]", redacted)
    return redacted


def _redact_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {**item, "summary_text": _redact_secrets(item.get("summary_text"))}
        for item in items
    ]


@dataclass(frozen=True)
class SecretaryMessage:
    message_id: str
    account: str
    subject: str
    from_addr: str
    to_addrs: str
    sent_at: str
    snippet: str
    body_path: str | None
    role: str | None
    priority_base: int
    labels: tuple[str, ...]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _case_terms(message: SecretaryMessage, body: str) -> str:
    return " ".join([message.subject, message.from_addr, message.snippet, body]).lower()


def _read_body(config: PipelineConfig, body_path: str | None) -> tuple[str, str]:
    if not body_path:
        return "", "subject+snippet"
    path = Path(body_path)
    if not path.is_absolute():
        path = config.workspace_root / path
    try:
        workspace_root = config.workspace_root.resolve(strict=False)
        resolved_path = path.resolve(strict=False)
    except OSError:
        return "", "subject+snippet/body-unavailable"
    if not resolved_path.is_relative_to(workspace_root):
        return "", "subject+snippet/body-outside-workspace"
    try:
        text = resolved_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", "subject+snippet/body-unavailable"
    text = re.sub(r"\s+", " ", text).strip()
    return text[:6000], "body+subject"


def _load_labels(conn: sqlite3.Connection, message_id: str) -> tuple[str, ...]:
    return tuple(row[0] for row in conn.execute("SELECT label FROM message_labels WHERE message_id = ?", (message_id,)).fetchall())


def _select_messages(config: PipelineConfig, *, since_minutes: int, limit: int, message_id: str | None = None) -> list[SecretaryMessage]:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).replace(microsecond=0).isoformat()
    params: list[Any] = []
    where = ["m.folder_kind = 'inbox'"]
    if message_id:
        where.append("m.message_id = ?")
        params.append(message_id)
    else:
        where.append("(m.ingested_at >= ? OR m.sent_at >= ?)")
        params.extend([cutoff, cutoff])
    query = f"""
        SELECT m.message_id, m.account, m.subject, m.from_addr, m.to_addrs, m.sent_at,
               m.snippet, m.body_path, si.role, COALESCE(si.priority_base, 0) AS priority_base
        FROM messages AS m
        LEFT JOIN sender_identities AS si ON lower(si.email) = lower(m.from_addr)
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(m.sent_at, m.ingested_at) DESC
        LIMIT ?
    """
    params.append(limit)
    with sqlite3.connect(config.database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return tuple(
            SecretaryMessage(
                message_id=row["message_id"],
                account=row["account"],
                subject=row["subject"] or "",
                from_addr=row["from_addr"] or "",
                to_addrs=row["to_addrs"] or "",
                sent_at=row["sent_at"] or "",
                snippet=row["snippet"] or "",
                body_path=row["body_path"],
                role=row["role"],
                priority_base=int(row["priority_base"] or 0),
                labels=_load_labels(conn, row["message_id"]),
            )
            for row in rows
        )


def _triage(message: SecretaryMessage, body: str, basis: str) -> dict[str, Any]:
    text = _case_terms(message, body)
    labels = set(message.labels)
    is_advisor = (message.role or "").lower() in {"advisor", "professor"} or "advisor-request" in labels
    has_action = is_advisor or any(term in text for term in ACTION_TERMS) or any(label in labels for label in ("direct-ask", "task", "meeting"))
    has_calendar = any(term in text for term in CALENDAR_TERMS) or "meeting" in labels
    has_task = any(term in text for term in TASK_TERMS) or "task" in labels
    is_noise = any(term in text for term in NOISE_TERMS) or any(label in labels for label in ("promotional-reference", "security-routine"))
    risk_hits = [term for term in RISK_TERMS if term in text]

    if risk_hits:
        risk_level = "high" if any(term in risk_hits for term in ("비밀번호", "password", "secret", "token", "api key", "송금", "계약", "법무")) else "medium"
    elif is_advisor or has_task:
        risk_level = "low"
    else:
        risk_level = "none"

    has_reply = any(term in text for term in ("회신", "답장", "reply", "respond")) or "direct-ask" in labels
    if has_calendar:
        action_type = "calendar"
    elif has_reply:
        action_type = "reply"
    elif has_task:
        action_type = "task"
    elif has_action:
        action_type = "reply"
    elif is_noise:
        action_type = "ignore"
    else:
        action_type = "read_only"

    if risk_level in {"medium", "high"}:
        triage_kind = "needs_user_context"
    elif action_type in {"reply", "calendar", "task"}:
        triage_kind = "action_ready"
    elif action_type == "ignore":
        triage_kind = "suppressed"
    else:
        triage_kind = "informational"

    priority = min(1.0, (0.25 if has_action else 0.05) + (0.25 if is_advisor else 0) + (message.priority_base / 200.0) + (0.15 if has_task else 0) + (0.1 if has_calendar else 0))
    if is_noise and not is_advisor:
        priority = min(priority, 0.25)
    confidence = 0.86 if basis.startswith("body") else 0.62
    if is_advisor:
        confidence += 0.06
    confidence = min(confidence, 0.96)
    source_text = body or message.snippet or message.subject
    excerpt = _redact_secrets(source_text)[:220]
    safe_subject = _redact_secrets(message.subject or "(제목 없음)")
    return {
        "triage_kind": triage_kind,
        "priority_score": round(priority, 3),
        "risk_level": risk_level,
        "action_required": bool(action_type in {"reply", "calendar", "task"}),
        "action_type": action_type,
        "meaning_summary": f"메일 본문/제목상 핵심은 '{safe_subject}' 관련 요청 또는 정보입니다." if source_text else "본문 근거가 부족해 제목 기준으로만 판단했습니다.",
        "impact_summary": "진왕님이 직접 확인하거나 승인하면 후속 대응으로 이어질 수 있습니다." if action_type in {"reply", "calendar", "task"} else "현재 즉시 외부 행동까지 필요하지 않은 정보성 신호입니다.",
        "risk_summary": ("민감/금전/계약/비밀 관련 표현이 있어 자동 대응 금지입니다: " + ", ".join(risk_hits[:5])) if risk_hits else "명시적 high-risk 표현은 발견하지 못했습니다.",
        "next_action_text": _next_action_text(action_type, risk_level),
        "analysis_basis": basis,
        "analysis_confidence": round(confidence, 3),
        "body_excerpt": excerpt,
        "reason": {"labels": sorted(labels), "advisor_like": is_advisor, "basis": basis},
    }


def _next_action_text(action_type: str, risk_level: str) -> str:
    if risk_level in {"medium", "high"}:
        return "초안은 만들 수 있으나 실제 발송/등록/확약 전 진왕님 판단이 필요합니다."
    if action_type == "reply":
        return "과거 회신 근거를 확인하고 회신 초안을 승인 요청으로 올립니다."
    if action_type == "calendar":
        return "일정 후보 초안을 만들고 캘린더 등록은 승인 전 금지합니다."
    if action_type == "task":
        return "작업 체크리스트 초안을 만들고 실행 여부를 승인 요청합니다."
    if action_type == "ignore":
        return "노이즈/정보성으로 보류합니다."
    return "읽어둘 정보로 기록하고 추가 행동은 보류합니다."


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','virtual table') AND name = ?", (name,)).fetchone() is not None


def _recall_evidence(conn: sqlite3.Connection, case_id: str, message: SecretaryMessage) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    subj = _norm(re.sub(r"^(re|fw|fwd)\s*:\s*", "", message.subject, flags=re.I))
    sender = _norm(message.from_addr)
    if subj:
        like = f"%{subj[:80]}%"
        sent_rows = conn.execute(
            """
            SELECT message_id, subject, sent_at FROM messages
            WHERE folder_kind = 'sent' AND (lower(subject) LIKE lower(?) OR lower(to_addrs) LIKE lower(?))
            ORDER BY sent_at DESC LIMIT 5
            """,
            (like, f"%{sender}%"),
        ).fetchall()
        for row in sent_rows:
            evidence.append({"source_table": "messages", "source_id": row[0], "evidence_kind": "sent_mail_history", "score": 0.82, "summary_text": _redact_secrets(f"과거 보낸메일 근거: {row[1]} ({row[2]})")})
    if _table_exists(conn, "knowledge_messages") and (subj or sender):
        rows = conn.execute(
            """
            SELECT knowledge_id, subject, semantic_summary_text, impact_text, next_action_text
            FROM knowledge_messages
            WHERE lower(subject) LIKE lower(?) OR lower(from_addr) = lower(?)
            ORDER BY collected_at DESC LIMIT 5
            """,
            (f"%{subj[:80]}%" if subj else "%%", sender),
        ).fetchall()
        for row in rows:
            summary = row[2] or row[3] or row[4] or row[1] or "knowledge recall"
            evidence.append({"source_table": "knowledge_messages", "source_id": row[0], "evidence_kind": "knowledge_recall", "score": 0.68, "summary_text": _redact_secrets(summary[:300])})
    return evidence[:8]


def _write_artifact(config: PipelineConfig, relative: Path, payload: str) -> Path:
    path = config.workspace_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def _approval_card(message: SecretaryMessage, case: dict[str, Any], evidence: list[dict[str, Any]], drafts: list[dict[str, Any]]) -> str:
    evidence_text = "; ".join(_redact_secrets(item["summary_text"]) for item in evidence[:3]) or "직접 일치하는 과거 처리 근거는 부족합니다."
    prepared = ", ".join(d["draft_type"] for d in drafts) or "no_action_note"
    safe_subject = _redact_secrets(message.subject)
    return (
        "[메일 행동 요청]\n"
        f"- 대상/메일: {message.from_addr} / {safe_subject}\n"
        f"- 핵심: {case['meaning_summary']}\n"
        f"- 과거 처리 근거: {evidence_text}\n"
        f"- 판단: {case['triage_kind']} · action={case['action_type']} · risk={case['risk_level']} · confidence={case['analysis_confidence']}\n"
        f"- 제가 준비한 것: {prepared}\n"
        "- 승인 필요: 실제 메일 발송/캘린더 등록/외부 task 생성은 아직 실행하지 않았고 승인 필요\n"
        f"- 진왕님 선택지: 승인 / 수정 지시 / 보류 / 거절 (case_id={case['case_id']})\n"
    )


def _drafts_for_case(
    config: PipelineConfig,
    message: SecretaryMessage,
    case: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    write_artifact: bool = True,
) -> list[dict[str, Any]]:
    action = case["action_type"]
    if action not in {"reply", "calendar", "task"}:
        return []
    draft_type = "reply" if action == "reply" else action
    external_effect = {"reply": "send_mail", "calendar": "create_calendar", "task": "create_task"}[action]
    draft_id = _hash_id("draft", case["case_id"], draft_type)
    base = Path("data/secretary/drafts") / f"{draft_id}.md"
    if draft_type == "reply":
        safe_from = _redact_secrets(message.from_addr)
        safe_subject = _redact_secrets(message.subject)
        body = (
            f"# 회신 초안\n\nTo: {safe_from}\nSubject: Re: {safe_subject}\n\n"
            "김재현 엔지니어님/담당자님께,\n\n메일 확인했습니다. 아래 사항 기준으로 확인 후 회신드리겠습니다.\n\n"
            f"- 제가 파악한 핵심: {case['meaning_summary']}\n"
            f"- 다음 액션: {case['next_action_text']}\n\n감사합니다.\n목진왕 드림\n"
        )
    else:
        body = json.dumps({"title": _redact_secrets(message.subject), "source_message_id": message.message_id, "next_action": case["next_action_text"], "evidence": _redact_evidence(evidence[:3])}, ensure_ascii=False, indent=2)
        base = base.with_suffix(".json")
    artifact_file = ""
    if write_artifact:
        artifact = _write_artifact(config, base, body)
        artifact_file = str(artifact.relative_to(config.workspace_root))
    return [{
        "draft_id": draft_id,
        "case_id": case["case_id"],
        "draft_type": draft_type,
        "status": "awaiting_approval",
        "title": _redact_secrets(message.subject),
        "body_md": body if draft_type == "reply" else "",
        "payload_json": json.dumps({"source_message_id": message.message_id, "external_effect": external_effect}, ensure_ascii=False),
        "external_effect": external_effect,
        "approval_required": 1,
        "confidence": case["analysis_confidence"],
        "artifact_file": artifact_file,
    }]


def generate_mail_secretary_cases(config: PipelineConfig, *, since_minutes: int = 30, limit: int = 20, message_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    messages = _select_messages(config, since_minutes=since_minutes, limit=limit, message_id=message_id)
    run_id = _hash_id("secretary-run", _now(), len(messages))
    now = _now()
    cases_out: list[dict[str, Any]] = []
    drafts_out: list[dict[str, Any]] = []
    cards: list[str] = []
    with sqlite3.connect(config.database_path) as conn:
        for message in messages:
            body, basis = _read_body(config, message.body_path)
            triage = _triage(message, body, basis)
            case_id = _hash_id("case", message.message_id)
            case = {"case_id": case_id, **triage}
            status = "awaiting_approval" if triage["action_type"] in {"reply", "calendar", "task"} else triage["triage_kind"]
            evidence = _recall_evidence(conn, case_id, message)
            drafts = _drafts_for_case(config, message, case, evidence, write_artifact=not dry_run)
            card = _approval_card(message, case, evidence, drafts) if drafts else ""
            case_record = {**case, "source_message_id": message.message_id, "status": status, "approval_card_md": card}
            cases_out.append(case_record)
            drafts_out.extend(drafts)
            if card:
                cards.append(card)
            if dry_run:
                continue
            conn.execute(
                """
                INSERT INTO mail_secretary_cases (
                    case_id, source_message_id, status, triage_kind, priority_score, risk_level,
                    action_required, action_type, meaning_summary, impact_summary, risk_summary,
                    next_action_text, analysis_basis, analysis_confidence, reason_json,
                    approval_card_md, created_at, updated_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(case_id) DO UPDATE SET
                    status = excluded.status,
                    triage_kind = excluded.triage_kind,
                    priority_score = excluded.priority_score,
                    risk_level = excluded.risk_level,
                    action_required = excluded.action_required,
                    action_type = excluded.action_type,
                    meaning_summary = excluded.meaning_summary,
                    impact_summary = excluded.impact_summary,
                    risk_summary = excluded.risk_summary,
                    next_action_text = excluded.next_action_text,
                    analysis_basis = excluded.analysis_basis,
                    analysis_confidence = excluded.analysis_confidence,
                    reason_json = excluded.reason_json,
                    approval_card_md = excluded.approval_card_md,
                    updated_at = excluded.updated_at
                """,
                (case_id, message.message_id, status, triage["triage_kind"], triage["priority_score"], triage["risk_level"], int(triage["action_required"]), triage["action_type"], triage["meaning_summary"], triage["impact_summary"], triage["risk_summary"], triage["next_action_text"], triage["analysis_basis"], triage["analysis_confidence"], json.dumps(triage["reason"], ensure_ascii=False), card, now, now),
            )
            conn.execute("DELETE FROM mail_secretary_evidence WHERE case_id = ?", (case_id,))
            for item in evidence:
                conn.execute(
                    "INSERT INTO mail_secretary_evidence (evidence_id, case_id, source_table, source_id, evidence_kind, score, summary_text, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (_hash_id("evidence", case_id, item["source_table"], item["source_id"], item["evidence_kind"]), case_id, item["source_table"], item["source_id"], item["evidence_kind"], item["score"], item["summary_text"], json.dumps(item, ensure_ascii=False), now),
                )
            for draft in drafts:
                conn.execute(
                    """
                    INSERT INTO mail_secretary_drafts (draft_id, case_id, draft_type, status, title, body_md, payload_json, external_effect, approval_required, confidence, artifact_file, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(draft_id) DO UPDATE SET status=excluded.status, title=excluded.title, body_md=excluded.body_md, payload_json=excluded.payload_json, external_effect=excluded.external_effect, approval_required=excluded.approval_required, confidence=excluded.confidence, artifact_file=excluded.artifact_file, updated_at=excluded.updated_at
                    """,
                    (draft["draft_id"], draft["case_id"], draft["draft_type"], draft["status"], draft["title"], draft["body_md"], draft["payload_json"], draft["external_effect"], draft["approval_required"], draft["confidence"], draft["artifact_file"], now, now),
                )
        conn.commit()
    artifact_payload = {"run_id": run_id, "generated_at": now, "case_count": len(cases_out), "draft_count": len(drafts_out), "needs_approval_count": len(cards), "cases": cases_out, "drafts": drafts_out, "approval_cards": cards}
    artifact_path = _write_artifact(config, Path("data/secretary/runs") / f"{run_id}.json", json.dumps(artifact_payload, ensure_ascii=False, indent=2))
    return {"run_id": run_id, "case_count": len(cases_out), "draft_count": len(drafts_out), "needs_approval_count": len(cards), "artifact_path": artifact_path, "approval_cards": cards, "cases": cases_out}


def review_mail_secretary_cases(config: PipelineConfig, *, status: str = "awaiting_approval", fmt: str = "json", limit: int = 20) -> dict[str, Any]:
    with sqlite3.connect(config.database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT c.case_id, c.source_message_id, c.status, c.triage_kind, c.action_type, c.risk_level,
                   c.meaning_summary, c.next_action_text, c.approval_card_md,
                   m.subject, m.from_addr
            FROM mail_secretary_cases AS c
            LEFT JOIN messages AS m ON m.message_id = c.source_message_id
            WHERE c.status = ?
            ORDER BY c.updated_at DESC LIMIT ?
            """,
            (status, limit),
        ).fetchall()
    cases = [dict(row) for row in rows]
    markdown = "\n".join(row.get("approval_card_md") or "" for row in cases).strip()
    if not markdown and fmt == "markdown":
        markdown = "신규로 허락 요청할 메일 case 없음."
    return {"case_count": len(cases), "cases": cases, "markdown": markdown}
