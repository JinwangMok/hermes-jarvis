from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from email import policy
from zoneinfo import ZoneInfo
from email.parser import BytesHeaderParser
from email.utils import getaddresses
from pathlib import Path
from typing import Callable

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig
from .mail import (
    _load_json_output,
    choose_all_mail_folder,
    normalize_envelope,
    parse_folder_list_table,
)

COMMON_CATEGORY_ORDER = [
    "opportunity",
    "technology",
    "research",
    "economy",
    "politics",
    "society",
    "culture",
    "admin",
    "security",
    "general",
]
CATEGORY_KEYWORDS = {
    "opportunity": [
        "모집", "공고", "지원", "신청", "접수", "참여 안내", "참가 안내", "registration", "register", "apply", "application", "call for", "submit", "challenge", "contest", "meetup", "summit", "fellowship", "grant", "funding", "startup", "인턴", "채용", "hackathon",
    ],
    "technology": [
        "ai", "agent", "llm", "mcp", "gpu", "nvidia", "openai", "anthropic", "databricks", "docker", "robot", "robotics", "openusd", "vla", "cloud", "semiconductor", "반도체", "기술", "데이터센터", "로보틱스",
    ],
    "research": [
        "seminar", "workshop", "conference", "paper", "research", "journal", "논문", "학회", "세미나", "연구", "isscc", "kics", "itrc",
    ],
    "economy": [
        "economy", "market", "stock", "etf", "gdp", "inflation", "oil", "receipt", "invoice", "투자", "증시", "주가", "금리", "환율", "유가", "영수증", "청약",
    ],
    "politics": [
        "election", "congress", "president", "government", "ministry", "policy", "war", "trump", "iran", "국회", "대통령", "정부", "정책", "전쟁", "외교", "개헌", "선거",
    ],
    "society": [
        "사회", "education", "safety", "폭력예방교육", "법정의무교육", "노동", "주거", "의료", "재난", "crime", "security alert", "startup weekly", "news",
    ],
    "culture": [
        "book", "movie", "music", "art", "newsletter", "review", "오라일리", "문화", "전시", "공연", "박람회",
    ],
    "admin": [
        "안내", "공지", "약관", "statement", "billing", "account", "login", "dropbox", "paypal", "slack", "docker", "godaddy", "cloudflare", "학사", "행정", "카드",
    ],
    "security": [
        "security alert", "reset password", "token was created", "로그인", "인증", "2단계", "alert", "application-specific password", "verify",
    ],
}
OPPORTUNITY_HINTS = set(CATEGORY_KEYWORDS["opportunity"])
HIGH_SIGNAL_SENDERS = {
    "1357@kised.or.kr",
    "wandb@mail.wandb.ai",
    "webadmin@kics.or.kr",
    "news@nvidia.com",
    "ad@okky.kr",
}
INTELLIGENCE_NOTE_DIR = "queries/jinwang-jarvis-intelligence"
CATEGORY_NOTE_DIR = f"{INTELLIGENCE_NOTE_DIR}/categories"
PRIORITY_NOTE_DIR = f"{INTELLIGENCE_NOTE_DIR}/priority"
INDEX_NOTE = f"{INTELLIGENCE_NOTE_DIR}/index.md"
JONGWON_SMARTX_FLOW_NOTE = f"{PRIORITY_NOTE_DIR}/jongwon-smartx-flow.md"
JONGWON_DIRECT_ACTIONS_NOTE = f"{PRIORITY_NOTE_DIR}/jongwon-direct-actions.md"
SMARTX_WEEKLY_BRIEFING_NOTE = f"{PRIORITY_NOTE_DIR}/smartx-weekly-briefing.md"
JONGWON_PHASE_MAP_NOTE = f"{PRIORITY_NOTE_DIR}/jongwon-phase-map.md"
JONGWON_CONTEXT_CASES_NOTE = f"{PRIORITY_NOTE_DIR}/jongwon-context-cases.md"
INTERACTION_CHAIN_NOTE = f"{PRIORITY_NOTE_DIR}/interaction-chain-status.md"
ADVISOR_ACTION_STATUS_NOTE = f"{PRIORITY_NOTE_DIR}/advisor-action-status.md"
PROJECT_WORK_ITEMS_NOTE = f"{PRIORITY_NOTE_DIR}/project-work-items.md"
RECENT_ACTION_ALERTS_NOTE = f"{PRIORITY_NOTE_DIR}/recent-action-alerts.md"
NEXT_DAY_MAIL_TODOS_NOTE = f"{PRIORITY_NOTE_DIR}/next-day-mail-todos.md"
EDUCATION_TEACHING_MEMORY_NOTE = f"{PRIORITY_NOTE_DIR}/education-teaching-memory.md"
MONTHLY_TIMELINE_NOTE = "queries/jinwang-jarvis-monthly-timeline-36m.md"
DEFAULT_LOOKBACK_DAYS = 7
MAIL_TODO_TIMEZONE = ZoneInfo("Asia/Seoul")
MAIL_TODO_CUTOFF_HOUR = 19
MAX_PAGES = 200
PAGE_SIZE = 100
JONGWON_ADDRESSES = {"jongwon@smartx.kr"}
SMARTX_SHARED_ADDRESSES = {"info@smartx.kr"}


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _default_runner(args: list[str]) -> str:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout


def _parse_himalaya_date(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _clean_subject(subject: str | None) -> str:
    text = (subject or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text or "(제목 없음)"


def _dedup_subject_key(subject: str | None) -> str:
    text = _clean_subject(subject).casefold()
    text = re.sub(r"^(re|fw|fwd)\s*:\s*", "", text)
    text = re.sub(r"\[[^\]]+\]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _categorize_subject(subject: str | None, sender: str | None) -> tuple[str, list[str], float, float]:
    cleaned = _clean_subject(subject)
    lowered = cleaned.casefold()
    sender = (sender or "").strip().lower()
    tags: list[str] = []
    category_scores = {key: 0.0 for key in COMMON_CATEGORY_ORDER}
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.casefold() in lowered:
                category_scores[category] += 1.0
                tags.append(keyword)
    if sender in HIGH_SIGNAL_SENDERS:
        category_scores["opportunity"] += 0.8
    if sender.endswith("substack.com") or sender.endswith("nytimes.com"):
        category_scores["society"] += 0.6
    if sender.endswith("technologyreview.kr") or sender.endswith("nvidia.com"):
        category_scores["technology"] += 0.6
    category = max(COMMON_CATEGORY_ORDER, key=lambda key: category_scores.get(key, 0.0))
    if category_scores[category] <= 0:
        category = "general"
    opportunity_score = 0.0
    for hint in OPPORTUNITY_HINTS:
        if hint.casefold() in lowered:
            opportunity_score += 0.22
    if sender in HIGH_SIGNAL_SENDERS:
        opportunity_score += 0.12
    if "마감" in cleaned or "deadline" in lowered or "d-" in lowered:
        opportunity_score += 0.18
    importance = min(1.0, 0.25 + category_scores.get(category, 0.0) * 0.12 + opportunity_score)
    if category in {"admin", "security"}:
        importance = max(0.05, importance - 0.2)
    return category, sorted(set(tags))[:8], round(importance, 3), round(min(1.0, opportunity_score), 3)


def _knowledge_summary(subject: str | None, category: str) -> str:
    cleaned = _clean_subject(subject)
    return f"[{category}] {cleaned}"


def _fetch_all_mail_rows(
    *,
    runner: Callable[[list[str]], str],
    account: str,
    folder_name: str,
    start: datetime,
    end: datetime,
    self_addresses: set[str] | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict]:
    collected: list[dict] = []
    seen_ids: set[str] = set()
    for page in range(1, MAX_PAGES + 1):
        args = [
            "himalaya", "envelope", "list", "-a", account,
            "--folder", folder_name,
            "--page", str(page),
            "--page-size", str(page_size),
            "--output", "json",
        ]
        try:
            page_rows = _load_json_output(runner(args))
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "") if hasattr(exc, "stderr") else ""
            if "out of bounds" in stderr.lower() or "out of bounds" in str(exc).lower():
                break
            raise
        if not page_rows:
            break
        page_in_window = 0
        oldest_dt: datetime | None = None
        for item in page_rows:
            normalized = normalize_envelope(account=account, folder_kind="knowledge", folder_name=folder_name, envelope=item, self_addresses=self_addresses)
            sent_dt = _parse_himalaya_date(normalized.get("date"))
            if sent_dt is None:
                continue
            oldest_dt = sent_dt if oldest_dt is None else min(oldest_dt, sent_dt)
            if sent_dt < start:
                continue
            if sent_dt > end:
                continue
            if normalized["message_id"] in seen_ids:
                continue
            seen_ids.add(normalized["message_id"])
            collected.append(normalized)
            page_in_window += 1
        if oldest_dt is not None and oldest_dt < start and page_in_window == 0:
            break
    return collected


def _upsert_knowledge_messages(database_path: Path, rows: list[dict]) -> None:
    with sqlite3.connect(database_path) as conn:
        for row in rows:
            category, tags, importance, opportunity_score = _categorize_subject(row.get("subject"), row.get("from_addr"))
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_messages (
                    knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr, to_addrs_json, cc_addrs_json,
                    self_role, interaction_role, sent_at, has_attachment, category, tags_json, importance_score,
                    opportunity_score, summary_text, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["message_id"],
                    row["account"],
                    row["folder_name"],
                    row["source_id"],
                    row.get("subject"),
                    row.get("from_addr"),
                    row.get("to_addr"),
                    json.dumps(row.get("to_addrs") or [], ensure_ascii=False),
                    json.dumps(row.get("cc_addrs") or [], ensure_ascii=False),
                    row.get("self_role"),
                    row.get("interaction_role"),
                    row.get("date"),
                    int(bool(row.get("has_attachment"))),
                    category,
                    json.dumps(tags, ensure_ascii=False),
                    importance,
                    opportunity_score,
                    _knowledge_summary(row.get("subject"), category),
                    _utc_now().isoformat(),
                ),
            )
        conn.commit()


def collect_knowledge_mail(
    config: PipelineConfig,
    *,
    months: int = 36,
    runner: Callable[[list[str]], str] | None = None,
) -> dict:
    bootstrap_workspace(config)
    runner = runner or _default_runner
    end = _utc_now()
    start = end - timedelta(days=months * 30)
    checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8")) if config.checkpoints_path.exists() else {}
    checkpoints.setdefault("knowledge_mail", {})
    all_rows: list[dict] = []
    account_summaries: list[dict] = []
    for account in config.accounts:
        folders = parse_folder_list_table(runner(["himalaya", "folder", "list", "-a", account]))
        all_mail_folder = choose_all_mail_folder(account, folders)
        rows = _fetch_all_mail_rows(runner=runner, account=account, folder_name=all_mail_folder, start=start, end=end, self_addresses=set(config.self_addresses))
        all_rows.extend(rows)
        checkpoints["knowledge_mail"][account] = {
            "all_mail_folder": all_mail_folder,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "collected_at": end.isoformat(),
            "message_count": len(rows),
        }
        account_summaries.append({"account": account, "all_mail_folder": all_mail_folder, "message_count": len(rows)})
    _upsert_knowledge_messages(config.database_path, all_rows)
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "message_count": len(all_rows),
        "accounts": account_summaries,
    }


def _load_recent_knowledge_rows(database_path: Path, *, as_of: datetime, lookback_days: int) -> list[dict]:
    start = (as_of - timedelta(days=lookback_days)).isoformat()
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr, to_addrs_json, cc_addrs_json,
                   self_role, interaction_role, sent_at, category, tags_json,
                   importance_score, opportunity_score, summary_text
            FROM knowledge_messages
            WHERE COALESCE(sent_at, '') >= ?
            ORDER BY opportunity_score DESC, importance_score DESC, sent_at DESC, knowledge_id ASC
            """,
            (start,),
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["tags"] = json.loads(item.get("tags_json") or "[]")
        item["to_addrs"] = json.loads(item.get("to_addrs_json") or "[]")
        item["cc_addrs"] = json.loads(item.get("cc_addrs_json") or "[]")
        cached_participants = _get_cached_message_participants(database_path, item)
        if cached_participants:
            item["references"] = cached_participants.get("references") or []
            item["message_id_header"] = cached_participants.get("message_id")
            item["in_reply_to"] = cached_participants.get("in_reply_to")
        else:
            item["references"] = []
            item["message_id_header"] = None
            item["in_reply_to"] = None
        payload.append(item)
    return payload


def _should_include_in_daily_report(row: dict) -> bool:
    subject = _clean_subject(row.get("subject"))
    lowered = subject.casefold()
    category = row.get("category") or "general"
    importance = float(row.get("importance_score") or 0.0)
    opportunity = float(row.get("opportunity_score") or 0.0)
    if "hermes test" in lowered:
        return False
    if category in {"admin", "security"} and opportunity < 0.25:
        return False
    if category == "general" and importance < 0.5 and opportunity < 0.25:
        return False
    return True


def _dedup_rows(rows: list[dict], *, limit: int) -> list[dict]:
    kept: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        key = _dedup_subject_key(row.get("subject"))
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
        if len(kept) >= limit:
            break
    return kept


def _is_jongwon_message(row: dict) -> bool:
    return (row.get("from_addr") or "").strip().lower() in JONGWON_ADDRESSES


def _is_smartx_shared_message(row: dict) -> bool:
    sender = (row.get("from_addr") or "").strip().lower()
    subject = _clean_subject(row.get("subject")).casefold()
    return sender in SMARTX_SHARED_ADDRESSES or "[smartx info]" in subject or "smartx info" in subject


def _is_action_like_subject(subject: str | None) -> bool:
    lowered = _clean_subject(subject).casefold()
    action_keywords = [
        "요청", "문의", "검토", "회신", "확인", "작성", "제출", "보고", "draft", "review", "submit", "action required",
    ]
    return any(keyword.casefold() in lowered for keyword in action_keywords)


def _is_security_or_ops_subject(subject: str | None) -> bool:
    lowered = _clean_subject(subject).casefold()
    return any(keyword in lowered for keyword in [
        "취약점", "보안", "ip 차단", "ip차단", "spoofing", "ssl", "tls", "인증서", "alert", "nfs", "troubleshooting", "ops", "server", "cluster", "react",
    ])


def _smartx_theme(subject: str | None) -> str:
    lowered = _clean_subject(subject).casefold()
    if _is_security_or_ops_subject(subject):
        return "security-ops"
    if any(keyword in lowered for keyword in ["dgx", "gpu", "dpu", "nvidia", "storage", "lakehouse", "iceberg", "data-bahn", "mcp", "openusd", "hpc"]):
        return "technology"
    if any(keyword in lowered for keyword in ["meetup", "summit", "webinar", "세미나", "심포지엄", "행사"]):
        return "event"
    return "general"


def _normalize_address_list(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        item = (value or "").strip().lower()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _classify_jongwon_context(row: dict, participants: dict[str, object], self_addresses: set[str]) -> str:
    sender = (row.get("from_addr") or "").strip().lower()
    to_addrs = set(_normalize_address_list(participants.get("to") if isinstance(participants.get("to"), list) else []))
    cc_addrs = set(_normalize_address_list(participants.get("cc") if isinstance(participants.get("cc"), list) else []))
    delivered_to = (participants.get("delivered_to") or row.get("to_addr") or "").strip().lower()
    self_set = {addr.strip().lower() for addr in self_addresses if addr.strip()} if self_addresses else set()
    if delivered_to:
        self_set.add(delivered_to)
    professor = "jongwon@smartx.kr"
    if sender == professor:
        if self_set & set(to_addrs) and len(to_addrs) == 1 and not cc_addrs:
            return "professor-sent-to-me-primary"
        if self_set & (to_addrs | cc_addrs | {delivered_to}):
            return "professor-sent-involving-me"
        return "professor-sent-other"
    if professor in to_addrs and self_set & cc_addrs:
        return "professor-primary-me-cc"
    if professor in cc_addrs and self_set & (to_addrs | {delivered_to}):
        return "professor-cced"
    if professor in to_addrs:
        return "professor-primary"
    if professor in cc_addrs:
        return "professor-cc-only"
    if _is_smartx_shared_message(row):
        return "smartx-shared"
    return "other"


def _header_addresses(values: list[str] | None) -> list[str]:
    parsed = [addr.lower() for _, addr in getaddresses(values or []) if addr]
    return _normalize_address_list(parsed)


def _parse_participant_headers(raw: bytes) -> dict[str, object]:
    parser = BytesHeaderParser(policy=policy.default)
    headers = parser.parsebytes(raw)
    delivered = (headers.get("Delivered-To") or "").strip().lower()
    refs = re.findall(r"<[^>]+>", " ".join(headers.get_all("References", [])))
    return {
        "to": _header_addresses(headers.get_all("To", [])),
        "cc": _header_addresses(headers.get_all("Cc", [])),
        "reply_to": _header_addresses(headers.get_all("Reply-To", [])),
        "delivered_to": delivered,
        "message_id": (headers.get("Message-ID") or "").strip() or None,
        "in_reply_to": (headers.get("In-Reply-To") or "").strip() or None,
        "references": refs,
    }


def _get_cached_message_participants(database_path: Path, row: dict) -> dict[str, object] | None:
    message_id = row.get("message_id")
    if not message_id:
        return None
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        cached = conn.execute(
            "SELECT to_addrs_json, cc_addrs_json, reply_to_addrs_json, delivered_to, references_json, message_id_header, in_reply_to FROM message_participant_cache WHERE message_id = ?",
            (message_id,),
        ).fetchone()
    if not cached:
        return None
    item = dict(cached)
    return {
        "to": json.loads(item.get("to_addrs_json") or "[]"),
        "cc": json.loads(item.get("cc_addrs_json") or "[]"),
        "reply_to": json.loads(item.get("reply_to_addrs_json") or "[]"),
        "delivered_to": item.get("delivered_to") or "",
        "references": json.loads(item.get("references_json") or "[]"),
        "message_id": item.get("message_id_header"),
        "in_reply_to": item.get("in_reply_to"),
    }


def _store_cached_message_participants(database_path: Path, row: dict, participants: dict[str, object], *, header_hash: str = "") -> None:
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO message_participant_cache (
                message_id, account, folder_name, source_id, to_addrs_json, cc_addrs_json,
                reply_to_addrs_json, delivered_to, references_json, message_id_header, in_reply_to, header_hash, cached_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("message_id"),
                row.get("account"),
                row.get("folder_name"),
                row.get("source_id"),
                json.dumps(participants.get("to") or [], ensure_ascii=False),
                json.dumps(participants.get("cc") or [], ensure_ascii=False),
                json.dumps(participants.get("reply_to") or [], ensure_ascii=False),
                participants.get("delivered_to") or "",
                json.dumps(participants.get("references") or [], ensure_ascii=False),
                participants.get("message_id") or None,
                participants.get("in_reply_to") or None,
                header_hash,
                _utc_now().isoformat(),
            ),
        )
        conn.commit()


def _export_message_raw(row: dict) -> bytes:
    account = row.get("account")
    folder_name = row.get("folder_name")
    source_id = row.get("source_id")
    if not account or not folder_name or not source_id:
        return b""
    with tempfile.NamedTemporaryFile(suffix=".eml", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "himalaya", "message", "export",
                "-a", str(account),
                str(source_id),
                "--folder", str(folder_name),
                "--full",
                "--destination", str(temp_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def _backfill_message_participant_cache(
    database_path: Path,
    rows: list[dict],
    *,
    exporter: Callable[[dict], bytes] | None = None,
    limit: int = 100,
) -> dict:
    exporter = exporter or _export_message_raw
    cached_count = 0
    scanned = 0
    for row in rows[:limit]:
        scanned += 1
        if _get_cached_message_participants(database_path, row):
            continue
        try:
            raw = exporter(row)
        except Exception:
            continue
        if not raw:
            continue
        participants = _parse_participant_headers(raw)
        _store_cached_message_participants(database_path, row, participants)
        cached_count += 1
    return {"scanned": scanned, "cached_count": cached_count}


def _load_uncached_participant_rows(database_path: Path, *, limit: int = 500) -> list[dict]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT km.knowledge_id AS message_id, km.account, km.folder_name, km.source_id,
                   km.subject, km.from_addr, km.to_addr, km.to_addrs_json, km.cc_addrs_json,
                   km.self_role, km.interaction_role, km.sent_at, km.importance_score, km.opportunity_score
            FROM knowledge_messages km
            LEFT JOIN message_participant_cache cache ON cache.message_id = km.knowledge_id
            WHERE cache.message_id IS NULL
            ORDER BY
                CASE WHEN km.interaction_role IN ('direct-ask', 'review-request', 'status-request', 'decision-request', 'fyi-forward') THEN 0 ELSE 1 END,
                COALESCE(km.importance_score, 0) DESC,
                COALESCE(km.opportunity_score, 0) DESC,
                COALESCE(km.sent_at, '') DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["to_addrs"] = json.loads(item.get("to_addrs_json") or "[]")
        item["cc_addrs"] = json.loads(item.get("cc_addrs_json") or "[]")
        payload.append(item)
    return payload


def _systematic_backfill_message_participant_cache(
    database_path: Path,
    *,
    exporter: Callable[[dict], bytes] | None = None,
    limit: int = 500,
) -> dict:
    candidates = _load_uncached_participant_rows(database_path, limit=limit)
    result = _backfill_message_participant_cache(database_path, candidates, exporter=exporter, limit=limit)
    return {
        "candidate_count": len(candidates),
        **result,
    }


def _load_message_participants(database_path: Path, row: dict) -> dict[str, object]:
    cached = _get_cached_message_participants(database_path, row)
    fallback = {
        "to": _normalize_address_list(row.get("to_addrs") if isinstance(row.get("to_addrs"), list) else [row.get("to_addr") or ""]),
        "cc": _normalize_address_list(row.get("cc_addrs") if isinstance(row.get("cc_addrs"), list) else []),
        "reply_to": [],
        "delivered_to": (row.get("to_addr") or "").strip().lower(),
        "references": row.get("references") or [],
        "message_id": row.get("message_id_header"),
        "in_reply_to": row.get("in_reply_to"),
    }
    if cached:
        merged = dict(fallback)
        merged.update({k: v for k, v in cached.items() if v not in (None, [], "")})
        return merged
    account = row.get("account")
    folder_name = row.get("folder_name")
    source_id = row.get("source_id")
    if not account or not folder_name or not source_id:
        return fallback
    try:
        with tempfile.NamedTemporaryFile(suffix=".eml", delete=False) as tmp:
            temp_path = Path(tmp.name)
        subprocess.run(
            [
                "himalaya", "message", "export",
                "-a", str(account),
                str(source_id),
                "--folder", str(folder_name),
                "--full",
                "--destination", str(temp_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        raw = temp_path.read_bytes()
        participants = _parse_participant_headers(raw)
        _store_cached_message_participants(database_path, row, participants)
        merged = dict(fallback)
        merged.update({k: v for k, v in participants.items() if v not in (None, [], "")})
        return merged
    except Exception:
        return fallback
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _flow_pattern(subject: str | None) -> str:
    lowered = _clean_subject(subject).casefold()
    if any(keyword in lowered for keyword in ["요청", "문의", "검토", "회신", "확인", "submit", "review"]):
        return "action-or-review"
    if any(keyword in lowered for keyword in ["예산", "연구비", "과제", "협약", "구매", "장비", "집행"]):
        return "budget-or-admin"
    if any(keyword in lowered for keyword in ["smartx info", "nvidia", "iceberg", "dgx", "dpu", "storage", "data-bahn", "mcp", "openusd", "hammerspace"]):
        return "technical-flow"
    if any(keyword in lowered for keyword in ["fwd:", "meetup", "summit", "모집", "공고", "행사", "심포지엄"]):
        return "opportunity-or-event"
    return "general"


def _infer_interaction_chains(rows: list[dict]) -> list[dict]:
    relevant_rows = [row for row in rows if row.get("interaction_role") not in {None, "other", "broadcast"}]
    id_index = {row.get("message_id_header"): row for row in relevant_rows if row.get("message_id_header")}
    groups: dict[str, list[dict]] = {}

    def group_key(row: dict) -> str:
        refs = row.get("references") or []
        if refs:
            return refs[0]
        if row.get("in_reply_to"):
            current = row.get("in_reply_to")
            seen = set()
            while current and current not in seen:
                seen.add(current)
                parent = id_index.get(current)
                if not parent:
                    return current
                parent_refs = parent.get("references") or []
                if parent_refs:
                    return parent_refs[0]
                current = parent.get("in_reply_to")
            return row.get("in_reply_to")
        if row.get("message_id_header"):
            return row.get("message_id_header")
        return _dedup_subject_key(row.get("subject"))

    for row in relevant_rows:
        groups.setdefault(group_key(row), []).append(row)

    results: list[dict] = []
    ask_roles = {"direct-ask", "review-request", "status-request", "decision-request"}
    awareness_roles = {"fyi-forward", "cc-for-awareness", "team-thread-update"}
    for key, items in groups.items():
        ordered = sorted(items, key=lambda row: row.get("sent_at") or "")
        last = ordered[-1]
        latest_ask_index = max(
            (idx for idx, row in enumerate(ordered) if row.get("interaction_role") in ask_roles and row.get("self_role") in {"direct-to-me", "cc-me", "other"}),
            default=-1,
        )
        latest_self_reply_index = max(
            (idx for idx, row in enumerate(ordered) if row.get("self_role") == "sent-by-me" and row.get("interaction_role") in {"status-reply", "fyi-forward", "team-thread-update"}),
            default=-1,
        )
        has_external_ask = latest_ask_index >= 0
        has_awareness_only = not has_external_ask and any(row.get("interaction_role") in awareness_roles for row in ordered)
        if not has_external_ask and not has_awareness_only:
            continue

        if has_awareness_only:
            state = "awareness-only"
        elif last.get("self_role") == "sent-by-me" and latest_self_reply_index >= latest_ask_index:
            state = "waiting-on-others"
        elif latest_self_reply_index >= 0 and latest_self_reply_index < latest_ask_index:
            state = "follow-up-pending"
        else:
            last_dt = _parse_himalaya_date(last.get("sent_at"))
            if last_dt and (_utc_now() - last_dt) > timedelta(days=30):
                state = "stale-open"
            else:
                state = "waiting-on-me"

        results.append({
            "subject_key": _dedup_subject_key(last.get("subject")),
            "thread_key": key,
            "state": state,
            "last_sent_at": last.get("sent_at"),
            "latest_subject": last.get("subject"),
            "participants": sorted({row.get("from_addr") for row in ordered if row.get("from_addr")}),
            "message_count": len(ordered),
            "messages": ordered,
        })
    order = {"waiting-on-me": 0, "follow-up-pending": 1, "stale-open": 2, "waiting-on-others": 3, "awareness-only": 4, "replied": 5}
    return sorted(results, key=lambda item: (order.get(item["state"], 9), item.get("last_sent_at") or ""), reverse=False)


def _load_jongwon_smartx_flow_rows(database_path: Path, *, as_of: datetime, months: int = 36) -> list[dict]:
    start = (as_of - timedelta(days=months * 30)).isoformat()
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr, to_addrs_json, cc_addrs_json,
                   self_role, interaction_role, sent_at, category, tags_json,
                   importance_score, opportunity_score, summary_text
            FROM knowledge_messages
            WHERE COALESCE(sent_at, '') >= ?
              AND (
                    LOWER(COALESCE(from_addr, '')) = 'jongwon@smartx.kr'
                 OR LOWER(COALESCE(from_addr, '')) = 'info@smartx.kr'
                 OR LOWER(COALESCE(subject, '')) LIKE '%[smartx info]%'
                 OR LOWER(COALESCE(subject, '')) LIKE '%smartx info%'
              )
            ORDER BY sent_at DESC, knowledge_id DESC
            """,
            (start,),
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["tags"] = json.loads(item.get("tags_json") or "[]")
        payload.append(item)
    return payload


def _load_recent_inbox_rows(database_path: Path, *, as_of: datetime, lookback_days: int = 7) -> list[dict]:
    start = (as_of - timedelta(days=lookback_days)).isoformat()
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT message_id, account, folder_kind, subject, from_addr, to_addrs, cc_addrs,
                   sent_at, snippet, self_role, interaction_role, is_seen
            FROM messages
            WHERE folder_kind = 'inbox'
              AND COALESCE(sent_at, '') >= ?
            ORDER BY sent_at DESC, message_id DESC
            """,
            (start,),
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        try:
            item['to_addrs'] = json.loads(item.get('to_addrs') or '[]')
        except Exception:
            item['to_addrs'] = []
        try:
            item['cc_addrs'] = json.loads(item.get('cc_addrs') or '[]')
        except Exception:
            item['cc_addrs'] = []
        payload.append(item)
    return payload


def _is_self_relay_action_candidate(row: dict) -> bool:
    subject = _clean_subject(row.get('subject')).casefold()
    sender = (row.get('from_addr') or '').strip().lower()
    if row.get('self_role') != 'sent-by-me' or row.get('interaction_role') != 'fyi-forward':
        return False
    if '@gm.gist.ac.kr' not in sender and '@gmail.com' not in sender:
        return False
    action_terms = [
        '응답 요청', '회신', '요청', '설문', '설문조사', '제출', '참석', '확정', '링크', '단톡방',
        'proposal', 'submission', 'shared', 'confirm', 'confirmed', 'remind', 'reminder', 'register',
    ]
    return any(term.casefold() in subject for term in action_terms)


def _build_recent_action_alerts(rows: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda item: item.get('sent_at') or '', reverse=True):
        subject = _clean_subject(row.get('subject'))
        key = _dedup_subject_key(subject)
        alert_type = None
        if row.get('self_role') in {'direct-to-me', 'cc-me'} and row.get('interaction_role') in {'direct-ask', 'review-request', 'status-request', 'decision-request'}:
            alert_type = 'direct-action'
        elif _is_self_relay_action_candidate(row):
            alert_type = 'self-relay-action'
        if not alert_type or key in seen:
            continue
        seen.add(key)
        alerts.append({
            'message_id': row.get('message_id'),
            'account': row.get('account'),
            'subject': subject,
            'from_addr': row.get('from_addr') or 'unknown',
            'sent_at': row.get('sent_at'),
            'alert_type': alert_type,
            'is_seen': row.get('is_seen'),
        })
    return alerts


def _write_recent_action_alerts_note(config: PipelineConfig, rows: list[dict], generated_at: str, *, as_of: datetime) -> Path:
    path = config.wiki_root / RECENT_ACTION_ALERTS_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    inbox_rows = _load_recent_inbox_rows(config.database_path, as_of=as_of, lookback_days=7)
    alerts = _build_recent_action_alerts(inbox_rows)
    direct_items = [item for item in alerts if item['alert_type'] == 'direct-action']
    relay_items = [item for item in alerts if item['alert_type'] == 'self-relay-action']
    lines = [
        '---',
        'title: Recent action alerts',
        f'created: {generated_at[:10]}',
        f'updated: {generated_at[:10]}',
        'type: query',
        'tags: [jarvis, intelligence, alerts, inbox, priority]',
        'sources: []',
        '---',
        '',
        '# Recent action alerts',
        '',
        '> 최근 inbox에서 즉시 확인이 필요한 direct mail과 self-relay forward action 후보를 모은 note.',
        '',
        '## Direct action mail',
    ]
    if direct_items:
        for item in direct_items[:20]:
            lines.append(f"- {item['sent_at']} | {item['subject']} | from={item['from_addr']} | seen={item['is_seen']}")
    else:
        lines.append('- none')
    lines.extend(['', '## Self-relay action candidates'])
    if relay_items:
        for item in relay_items[:20]:
            lines.append(f"- {item['sent_at']} | {item['subject']} | from={item['from_addr']} | seen={item['is_seen']}")
    else:
        lines.append('- none')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def _mail_todo_window(as_of: datetime) -> tuple[datetime, datetime, datetime, datetime]:
    local_as_of = as_of.astimezone(MAIL_TODO_TIMEZONE)
    local_cutoff = local_as_of.replace(hour=MAIL_TODO_CUTOFF_HOUR, minute=0, second=0, microsecond=0)
    if local_as_of < local_cutoff:
        local_cutoff -= timedelta(days=1)
    local_start = local_cutoff - timedelta(days=1)
    return (
        local_start.astimezone(UTC),
        local_cutoff.astimezone(UTC),
        local_start,
        local_cutoff,
    )


def _load_mail_rows_for_todo_window(database_path: Path, *, as_of: datetime) -> list[dict]:
    start_utc, end_utc, _, _ = _mail_todo_window(as_of)
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT message_id, account, folder_kind, subject, from_addr, to_addrs, cc_addrs,
                   sent_at, snippet, self_role, interaction_role, is_seen
            FROM messages
            WHERE datetime(COALESCE(sent_at, '')) >= datetime(?)
              AND datetime(COALESCE(sent_at, '')) < datetime(?)
            ORDER BY datetime(sent_at) DESC, message_id DESC
            """,
            (start_utc.isoformat(), end_utc.isoformat()),
        ).fetchall()
    payload: list[dict] = []
    for row in rows:
        item = dict(row)
        try:
            item['to_addrs'] = json.loads(item.get('to_addrs') or '[]')
        except Exception:
            item['to_addrs'] = []
        try:
            item['cc_addrs'] = json.loads(item.get('cc_addrs') or '[]')
        except Exception:
            item['cc_addrs'] = []
        payload.append(item)
    return payload


def _infer_mail_todo_action(subject: str) -> str:
    lowered = _clean_subject(subject).casefold()
    if any(term in lowered for term in ['google account', 'account settings', 'security', 'verify', 'review your google account']):
        return '계정/보안 설정을 검토하고 필요한 조치를 정리'
    if any(term in lowered for term in ['서버 접근', '접근 안내', 'access', 'server']):
        return '접근 요청/안내 상태를 확인하고 필요한 회신·후속 조치를 정리'
    if any(term in lowered for term in ['설문', '응답 요청', '응답', 'survey']):
        return '응답/설문 제출 여부를 결정하고 처리'
    if any(term in lowered for term in ['참석', 'confirmed', 'confirm', 'registration', 'register', '참가']):
        return '참석 여부·등록 상태를 확인하고 필요한 준비를 정리'
    if any(term in lowered for term in ['proposal', 'submission', 'shared', 'compilation']):
        return '공유된 제안/제출 자료를 확인하고 필요한 후속 작업을 정리'
    if any(term in lowered for term in ['링크', '단톡방', 'link']):
        return '전달된 링크를 확인하고 참여/공유가 필요한지 정리'
    if any(term in lowered for term in ['일지', '보고']):
        return '정기 보고/업무 일지 관련 남은 조치를 확인'
    if any(term in lowered for term in ['remind', 'reminder', '요청']):
        return '요청 메일의 남은 액션을 확인하고 우선순위를 정리'
    return '메일 내용을 확인하고 필요한 후속 조치를 정리'


def _build_next_day_mail_todos(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    actionable: list[dict] = []
    awareness: list[dict] = []
    seen_subjects: set[str] = set()
    alerts = _build_recent_action_alerts(rows)
    alert_index = {item['message_id']: item for item in alerts if item.get('message_id')}
    for row in sorted(rows, key=lambda item: item.get('sent_at') or '', reverse=True):
        subject = _clean_subject(row.get('subject'))
        if subject == '(제목 없음)':
            continue
        dedup_key = _dedup_subject_key(subject)
        if dedup_key in seen_subjects:
            continue
        seen_subjects.add(dedup_key)
        alert = alert_index.get(row.get('message_id'))
        lowered = subject.casefold()
        is_action = alert is not None or row.get('interaction_role') in {'direct-ask', 'review-request', 'status-request', 'decision-request'}
        if not is_action:
            is_action = any(term in lowered for term in ['응답 요청', '설문', 'proposal', 'submission', 'confirmed', '참석', '링크', '단톡방', 'server', 'access', 'review'])
        item = {
            'message_id': row.get('message_id'),
            'account': row.get('account'),
            'folder_kind': row.get('folder_kind'),
            'subject': subject,
            'from_addr': row.get('from_addr') or 'unknown',
            'sent_at': row.get('sent_at') or 'unknown',
            'alert_type': alert.get('alert_type') if alert else None,
            'todo': _infer_mail_todo_action(subject),
        }
        if is_action:
            actionable.append(item)
        elif row.get('folder_kind') == 'inbox':
            awareness.append(item)
    return actionable[:12], awareness[:8]


def _write_next_day_mail_todos_note(config: PipelineConfig, generated_at: str, *, as_of: datetime) -> Path:
    path = config.wiki_root / NEXT_DAY_MAIL_TODOS_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    window_rows = _load_mail_rows_for_todo_window(config.database_path, as_of=as_of)
    actionable, awareness = _build_next_day_mail_todos(window_rows)
    _, _, local_start, local_end = _mail_todo_window(as_of)
    inbox_count = sum(1 for row in window_rows if row.get('folder_kind') == 'inbox')
    sent_count = sum(1 for row in window_rows if row.get('folder_kind') == 'sent')
    lines = [
        '---',
        'title: Next-day TODO from mail',
        f'created: {generated_at[:10]}',
        f'updated: {generated_at[:10]}',
        'type: query',
        'tags: [jarvis, intelligence, todo, mail, priority]',
        'sources: []',
        '---',
        '',
        '# Next-day TODO from mail',
        '',
        '> 전날 19시부터 오늘 19시까지 들어오고 오간 메일만 기준으로, 다음날 챙길 TODO를 메일 중심으로 정리한 note.',
        '',
        f"- Window (KST): {local_start.strftime('%Y-%m-%d %H:%M')} ~ {local_end.strftime('%Y-%m-%d %H:%M')}",
        f"- Messages reviewed: total={len(window_rows)}, inbox={inbox_count}, sent={sent_count}",
        f"- Strong action candidates: {len(actionable)}",
        '',
        '## Strong mail signals',
    ]
    if actionable:
        for item in actionable:
            signal = item['alert_type'] or item['folder_kind'] or 'mail'
            lines.append(f"- [{signal}] {item['subject']} | from={item['from_addr']} | sent={item['sent_at']}")
    else:
        lines.append('- none')
    lines.extend(['', '## Draft TODO for tomorrow'])
    if actionable:
        for item in actionable:
            lines.append(f"- [ ] {item['todo']} — 근거: {item['subject']}")
    else:
        lines.append('- [ ] 특별히 급한 메일 TODO는 보이지 않음. 미처리 direct/self-relay 메일만 다시 확인')
    lines.extend(['', '## Lower-priority awareness'])
    if awareness:
        for item in awareness:
            lines.append(f"- {item['subject']} | from={item['from_addr']} | sent={item['sent_at']}")
    else:
        lines.append('- none')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def _write_jongwon_smartx_flow_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / JONGWON_SMARTX_FLOW_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    jongwon_rows = [row for row in rows if _is_jongwon_message(row)]
    smartx_rows = [row for row in rows if _is_smartx_shared_message(row)]
    pattern_counts: dict[str, int] = {}
    monthly_counts: dict[str, int] = {}
    monthly_split: dict[str, dict[str, int]] = {}
    for row in rows:
        pattern = _flow_pattern(row.get("subject"))
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        ym = (row.get("sent_at") or "")[:7]
        if ym:
            monthly_counts[ym] = monthly_counts.get(ym, 0) + 1
            slot = monthly_split.setdefault(ym, {"jongwon": 0, "smartx_shared": 0, "total": 0})
            slot["total"] += 1
            if _is_jongwon_message(row):
                slot["jongwon"] += 1
            if _is_smartx_shared_message(row):
                slot["smartx_shared"] += 1
    top_months = sorted(monthly_counts.items(), key=lambda item: (-item[1], item[0]))[:12]
    recent_jongwon = _dedup_rows(jongwon_rows, limit=12)
    recent_smartx = _dedup_rows(smartx_rows, limit=12)
    lines = [
        "---",
        "title: Jongwon + SmartX mail flow",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, jongwon, smartx, priority]",
        "sources: []",
        "---",
        "",
        "# Jongwon + SmartX mail flow",
        "",
        "> Priority note: 교수님 직접 메일과 SmartX 전체 기술 공유 흐름을 장기적으로 추적하는 핵심 note.",
        "",
        "## Summary",
        f"- direct mails from jongwon@smartx.kr (36m): {len(jongwon_rows)}",
        f"- SmartX shared / [SmartX Info] mails (36m): {len(smartx_rows)}",
        f"- total tracked priority flow items (36m): {len(rows)}",
        "",
        "## Related notes",
        f"- [[{JONGWON_DIRECT_ACTIONS_NOTE.removesuffix('.md')}]]",
        f"- [[{SMARTX_WEEKLY_BRIEFING_NOTE.removesuffix('.md')}]]",
        f"- [[{JONGWON_PHASE_MAP_NOTE.removesuffix('.md')}]]",
        f"- [[{JONGWON_CONTEXT_CASES_NOTE.removesuffix('.md')}]]",
        "",
        "## Pattern mix",
    ]
    for name, count in sorted(pattern_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Recent direct mails from jongwon@smartx.kr"])
    if recent_jongwon:
        for row in recent_jongwon:
            lines.append(f"- {row['sent_at']} — {row['subject']} ({row['category']})")
    else:
        lines.append("- none")
    lines.extend(["", "## Recent SmartX shared flow"])
    if recent_smartx:
        for row in recent_smartx:
            lines.append(f"- {row['sent_at']} — {row['subject']} ({row['from_addr'] or 'unknown'})")
    else:
        lines.append("- none")
    lines.extend(["", "## Monthly direct vs shared flow", "- Note: direct and shared counts can overlap when jongwon@smartx.kr forwarded or sent SmartX shared flow."])
    for ym in sorted(monthly_split):
        slot = monthly_split[ym]
        lines.append(
            f"- {ym}: direct={slot['jongwon']}, shared={slot['smartx_shared']}, total={slot['total']}"
        )
    lines.extend(["", "## Monthly flow hotspots"])
    for ym, count in top_months:
        month_examples = _dedup_rows([row for row in rows if (row.get("sent_at") or "")[:7] == ym], limit=3)
        example_text = "; ".join(_clean_subject(item.get("subject")) for item in month_examples)
        lines.append(f"- {ym}: {count} mails — {example_text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_jongwon_direct_actions_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / JONGWON_DIRECT_ACTIONS_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    direct_rows = [row for row in rows if _is_jongwon_message(row)]
    action_rows = _dedup_rows([row for row in direct_rows if _is_action_like_subject(row.get("subject")) or float(row.get("opportunity_score") or 0.0) >= 0.3], limit=50)
    lines = [
        "---",
        "title: Jongwon direct actions",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, jongwon, actions, priority]",
        "sources: []",
        "---",
        "",
        "# Jongwon direct actions",
        "",
        "> 교수님이 직접 보낸 메일 중 요청/검토/피드백/행사 forwarding 성격이 강한 메일을 우선 모아둔 note.",
        "",
        f"- total direct mails in 36m: {len(direct_rows)}",
        f"- action-like mails selected: {len(action_rows)}",
        "",
        "## Action-like mails",
    ]
    for row in action_rows:
        lines.append(f"- {row['sent_at']} — {row['subject']} ({row['category']})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_smartx_weekly_briefing_note(config: PipelineConfig, rows: list[dict], generated_at: str, *, as_of: datetime) -> Path:
    path = config.wiki_root / SMARTX_WEEKLY_BRIEFING_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    cutoff = (as_of - timedelta(days=7)).isoformat()
    weekly_rows = [row for row in rows if _is_smartx_shared_message(row) and (row.get('sent_at') or '') >= cutoff]
    security_ops = _dedup_rows([row for row in weekly_rows if _smartx_theme(row.get('subject')) == 'security-ops'], limit=12)
    technology = _dedup_rows([row for row in weekly_rows if _smartx_theme(row.get('subject')) == 'technology'], limit=12)
    events = _dedup_rows([row for row in weekly_rows if _smartx_theme(row.get('subject')) == 'event'], limit=8)
    lines = [
        "---",
        "title: SmartX weekly briefing",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, smartx, weekly, priority]",
        "sources: []",
        "---",
        "",
        "# SmartX weekly briefing",
        "",
        "> 최근 7일간 SmartX shared 흐름 중 연구실 전체 기술/운영 문맥 파악에 중요한 메일을 묶은 note.",
        "",
        f"- weekly shared items: {len(weekly_rows)}",
        "",
        "## Security / ops watch",
    ]
    if security_ops:
        for row in security_ops:
            lines.append(f"- {row['sent_at']} — {row['subject']} ({row['from_addr'] or 'unknown'})")
    else:
        lines.append("- none")
    lines.extend(["", "## Technology watch"])
    if technology:
        for row in technology:
            lines.append(f"- {row['sent_at']} — {row['subject']} ({row['from_addr'] or 'unknown'})")
    else:
        lines.append("- none")
    lines.extend(["", "## Event / opportunity watch"])
    if events:
        for row in events:
            lines.append(f"- {row['sent_at']} — {row['subject']} ({row['from_addr'] or 'unknown'})")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _phase_for_month(*, direct: int, shared: int, rows: list[dict]) -> str:
    subjects = ' '.join(_clean_subject(row.get('subject')).casefold() for row in rows)
    if any(keyword in subjects for keyword in ['예산', '연구비', '협약', '참여율', '제안서', '작성', '제출']):
        return 'execution-admin'
    if any(keyword in subjects for keyword in ['dgx', 'gpu', 'nfs', 'storage', 'iceberg', 'data-bahn', 'cluster', 'server', 'dpu']):
        return 'infra-buildout'
    if shared >= direct:
        return 'shared-tech-radar'
    if direct >= 20:
        return 'advisor-driven-execution'
    return 'mixed-followups'


def _write_jongwon_phase_map_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / JONGWON_PHASE_MAP_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    monthly: dict[str, list[dict]] = {}
    for row in rows:
        ym = (row.get('sent_at') or '')[:7]
        if ym:
            monthly.setdefault(ym, []).append(row)
    lines = [
        "---",
        "title: Jongwon phase map",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, jongwon, phase-map, priority]",
        "sources: []",
        "---",
        "",
        "# Jongwon phase map",
        "",
        "> 교수님 direct + SmartX shared 흐름을 월별 phase로 압축한 note.",
        "",
        "## Monthly phase map",
    ]
    for ym in sorted(monthly):
        month_rows = monthly[ym]
        direct = sum(1 for row in month_rows if _is_jongwon_message(row))
        shared = sum(1 for row in month_rows if _is_smartx_shared_message(row))
        phase = _phase_for_month(direct=direct, shared=shared, rows=month_rows)
        examples = '; '.join(_clean_subject(row.get('subject')) for row in _dedup_rows(month_rows, limit=2))
        lines.append(f"- {ym} — {phase} | direct={direct}, shared={shared} | {examples}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_jongwon_context_cases_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / JONGWON_CONTEXT_CASES_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate_rows = _dedup_rows([
        row for row in rows
        if _is_jongwon_message(row) or _is_smartx_shared_message(row) or (row.get('to_addr') or '').strip().lower() == 'jongwon@smartx.kr'
    ], limit=40)
    grouped: dict[str, list[dict]] = {}
    self_addresses = set(config.self_addresses)
    for row in candidate_rows:
        relation = _classify_jongwon_context(row, _load_message_participants(config.database_path, row), self_addresses)
        grouped.setdefault(relation, []).append(row)
    lines = [
        "---",
        "title: Jongwon context cases",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, jongwon, context, priority]",
        "sources: []",
        "---",
        "",
        "# Jongwon context cases",
        "",
        "> 교수님 관련 메일을 발신/수신/참조 관계로 나눠서 최근 중요 케이스를 보는 note.",
    ]
    for relation in [
        "professor-sent-to-me-primary",
        "professor-sent-involving-me",
        "professor-primary-me-cc",
        "professor-cced",
        "professor-primary",
        "professor-cc-only",
        "professor-sent-other",
        "smartx-shared",
    ]:
        lines.extend(["", f"## {relation}"])
        items = grouped.get(relation, [])
        if not items:
            lines.append("- none")
            continue
        for row in items[:10]:
            lines.append(f"- {row['sent_at']} — {row['subject']} ({row['from_addr'] or 'unknown'} -> {row.get('to_addr') or 'unknown'})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_interaction_chain_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / INTERACTION_CHAIN_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    chains = _infer_interaction_chains(rows)
    lines = [
        "---",
        "title: Interaction chain status",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, chains, priority]",
        "sources: []",
        "---",
        "",
        "# Interaction chain status",
        "",
        "> 요청-응답-후속질문 흐름을 thread relation 기준으로 추정한 note.",
    ]
    for state in ["waiting-on-me", "follow-up-pending", "stale-open", "waiting-on-others", "awareness-only"]:
        lines.extend(["", f"## {state}"])
        items = [item for item in chains if item["state"] == state]
        if not items:
            lines.append("- none")
            continue
        for item in items[:20]:
            participants = ", ".join(item.get("participants") or [])
            lines.append(f"- {item['latest_subject']} | messages={item['message_count']} | participants={participants} | last={item['last_sent_at']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_advisor_action_status_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / ADVISOR_ACTION_STATUS_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    professor_rows = [row for row in rows if (row.get('from_addr') or '').strip().lower() == 'jongwon@smartx.kr']
    chains = _infer_interaction_chains(professor_rows)
    do_now = [item for item in chains if item['state'] in {'waiting-on-me', 'follow-up-pending', 'stale-open'}]
    waiting_on_others = [item for item in chains if item['state'] == 'waiting-on-others']
    awareness = [item for item in chains if item['state'] == 'awareness-only']
    lines = [
        "---",
        "title: Advisor action status",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, advisor, action, priority]",
        "sources: []",
        "---",
        "",
        "# Advisor action status",
        "",
        "> 교수님 관련 메일 중 실제 할 일 / 회신 대기 / awareness를 구분해 보는 note.",
        "",
        "## do-now",
    ]
    if do_now:
        for item in do_now[:20]:
            lines.append(f"- {item['latest_subject']} | state={item['state']} | last={item['last_sent_at']}")
    else:
        lines.append("- none")
    lines.extend(["", "## waiting-on-others"])
    if waiting_on_others:
        for item in waiting_on_others[:20]:
            lines.append(f"- {item['latest_subject']} | state={item['state']} | last={item['last_sent_at']}")
    else:
        lines.append("- none")
    lines.extend(["", "## awareness-only"])
    if awareness:
        for item in awareness[:20]:
            lines.append(f"- {item['latest_subject']} | state={item['state']} | last={item['last_sent_at']}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _project_bucket(subject: str | None) -> str:
    lowered = _clean_subject(subject).casefold()
    if any(keyword in lowered for keyword in ['data-bahn', '데이터 파이프라인', '데이터스키마', 'lakehouse']):
        return 'data-platform'
    if any(keyword in lowered for keyword in ['제안서', '사업계획서', '평가', '발표자료', 'innocore']):
        return 'proposal-and-evaluation'
    if any(keyword in lowered for keyword in ['교원연수', '교육자료', '교과서', 'star-mooc']):
        return 'education-programs'
    if any(keyword in lowered for keyword in ['특허', '출원']):
        return 'patent-and-ip'
    return 'general'


def _build_project_work_items(rows: list[dict], chains: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for chain in chains:
        bucket = _project_bucket(chain.get('latest_subject'))
        if bucket == 'general':
            continue
        slot = grouped.setdefault(bucket, {
            'bucket': bucket,
            'items': [],
            'states': set(),
            'latest_at': '',
        })
        slot['items'].append(chain)
        slot['states'].add(chain.get('state'))
        slot['latest_at'] = max(slot['latest_at'], chain.get('last_sent_at') or '')
    result = []
    for bucket, slot in grouped.items():
        examples = '; '.join(item.get('latest_subject') or '' for item in slot['items'][:3])
        result.append({
            'bucket': bucket,
            'latest_at': slot['latest_at'],
            'state_mix': ', '.join(sorted(state for state in slot['states'] if state)),
            'count': len(slot['items']),
            'examples': examples,
        })
    return sorted(result, key=lambda item: (item['latest_at'], item['count']), reverse=True)


def _write_project_work_items_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / PROJECT_WORK_ITEMS_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    chains = _infer_interaction_chains(rows)
    items = _build_project_work_items(rows, chains)
    lines = [
        "---",
        "title: Project work items",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, projects, work-items, priority]",
        "sources: []",
        "---",
        "",
        "# Project work items",
        "",
        "> 메일 체인을 프로젝트/업무 단위로 묶어 보는 canonical note.",
        "",
        "## Active work items",
    ]
    if items:
        for item in items[:20]:
            lines.append(f"- {item['bucket']} | states={item['state_mix']} | count={item['count']} | latest={item['latest_at']} | examples={item['examples']}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _load_education_memory_rows(database_path: Path, *, months: int = 36) -> list[dict]:
    pattern = '(교육|강의|교원연수|교과서|고등학교|고교|특강|수업|직장인|일반인|기업가정신교육|연수|강사료|드림ai|dream ai|star-mooc|인공지능 교과서)'
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.create_function('regexp', 2, lambda p, text: 1 if text and __import__('re').search(p, text, __import__('re').I) else 0)
        rows = conn.execute(
            """
            SELECT knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr, to_addrs_json, cc_addrs_json,
                   self_role, interaction_role, sent_at, category, tags_json, importance_score, opportunity_score, summary_text
            FROM knowledge_messages
            WHERE lower(coalesce(subject,'')) regexp ?
            ORDER BY sent_at DESC
            """,
            (pattern,),
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item['tags'] = json.loads(item.get('tags_json') or '[]')
        item['to_addrs'] = json.loads(item.get('to_addrs_json') or '[]')
        item['cc_addrs'] = json.loads(item.get('cc_addrs_json') or '[]')
        payload.append(item)
    return payload


def _normalize_education_event_name(subject: str | None) -> str:
    text = _clean_subject(subject)
    text = re.sub(r'^(re|fw|fwd)\s*:\s*', '', text, flags=re.I)
    text = re.sub(r'\.(zip|pdf|pptx|ppt|docx|doc|xlsx|xls)$', '', text, flags=re.I)
    return text.strip()


def _is_generic_education_notice(subject: str | None, sender: str | None) -> bool:
    lowered = _normalize_education_event_name(subject).casefold()
    sender_value = (sender or '').strip().lower()
    generic_keywords = [
        '도서관 이용자 교육', '이용자 교육', '정기교육', '법정의무교육', '폭력예방교육',
        'proquest', 'refworks', 'web of science', 'scopus', 'sci val', 'scival', 'riss',
        '클래리베이트', '안전교육', '보안교육', '연구윤리 교육', '수강 안내', '모집 안내',
        '교육생 모집', '파견 교육생 모집', '대국민 공공데이터 인식 제고 교육',
        '정신건강특강', '상담센터', '여교수회 기획특강',
    ]
    if any(keyword.casefold() in lowered for keyword in generic_keywords):
        return True
    if sender_value.endswith('discover.clarivate.com'):
        return True
    if '광고' in lowered and '교육' in lowered:
        return True
    return False


def _education_audience(subject: str | None) -> str:
    lowered = _normalize_education_event_name(subject).casefold()
    if any(keyword in lowered for keyword in ['고등학교', '고교', '중등']):
        return 'high-school'
    if any(keyword in lowered for keyword in ['교원연수', '교원 연수', '교원']):
        return 'teachers'
    if any(keyword in lowered for keyword in ['직장인', '기업가정신교육', 'ict insight day']):
        return 'workers'
    if any(keyword in lowered for keyword in ['일반인', '대국민', '시민']):
        return 'public'
    if any(keyword in lowered for keyword in ['대학원생', '학부생', '학생용', '학생']):
        return 'students'
    return 'mixed'


def _education_role(subject: str | None, row: dict) -> str:
    lowered = _normalize_education_event_name(subject).casefold()
    if any(keyword in lowered for keyword in ['교과서', '교육자료', '교수학습 모델', '프루프리딩', '원격 피드백']):
        return 'textbook-development'
    if any(keyword in lowered for keyword in ['강의 자료', '강의자료', '교안', '사전질문', 'star-mooc', '촬영', '인강', '교수학습자료']):
        return 'teaching-delivery'
    if any(keyword in lowered for keyword in ['교원연수', '강사료', '운영', '일정 조정', '일정표', '결과 보고', '준비 관련 안내', '기업가정신교육']):
        return 'instruction-support'
    interaction_role = (row.get('interaction_role') or '').strip().lower()
    if interaction_role in {'direct-ask', 'review-request', 'status-request', 'decision-request'} and any(
        keyword in lowered for keyword in ['교육자료', '교과서', '교원연수', '강의 자료', '강의자료', '교안', '사전질문', '촬영', '인강', '기업가정신교육']
    ):
        return 'instruction-support'
    return 'education-other'


def _education_summary(subject: str | None, role: str) -> str:
    lowered = _normalize_education_event_name(subject).casefold()
    if role == 'textbook-development':
        return '교과서/교육자료 개발 또는 검토 흐름'
    if role == 'teaching-delivery':
        return '강의/교안/콘텐츠 전달 준비 흐름'
    if role == 'instruction-support':
        if '교원연수' in lowered:
            return '교원연수 운영·정산·보고 관련 흐름'
        return '교육 운영·조율·행정 지원 흐름'
    return '교육 관련 흔적'


def _build_education_memory_records(rows: list[dict]) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda item: item.get('sent_at') or '', reverse=True):
        subject = row.get('subject')
        if _is_generic_education_notice(subject, row.get('from_addr')):
            continue
        role = _education_role(subject, row)
        if role == 'education-other':
            continue
        event_name = _normalize_education_event_name(subject)
        key = _dedup_subject_key(event_name)
        if key in seen:
            continue
        seen.add(key)
        records.append({
            'knowledge_id': row.get('knowledge_id'),
            'sent_at': row.get('sent_at'),
            'date': (row.get('sent_at') or '')[:10],
            'month': (row.get('sent_at') or '')[:7],
            'event_name': event_name,
            'audience': _education_audience(subject),
            'role': role,
            'summary': _education_summary(subject, role),
            'from_addr': row.get('from_addr') or 'unknown',
            'subject': _clean_subject(subject),
        })
    return records


def _build_education_cv_sections(records: list[dict]) -> dict[str, list[dict]]:
    sections = {
        'teaching-delivery': [],
        'textbook-development': [],
        'instruction-support': [],
        'timeline': sorted(records, key=lambda item: item.get('sent_at') or '', reverse=True),
    }
    for record in records:
        role = record.get('role')
        if role in sections:
            sections[role].append(record)
    return sections


def _write_education_teaching_memory_note(config: PipelineConfig, rows: list[dict], generated_at: str) -> Path:
    path = config.wiki_root / EDUCATION_TEACHING_MEMORY_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    edu_rows = _load_education_memory_rows(config.database_path)
    records = _build_education_memory_records(edu_rows)
    sections = _build_education_cv_sections(records)
    by_audience: dict[str, list[dict]] = {}
    for record in records:
        by_audience.setdefault(record['audience'], []).append(record)
    lines = [
        "---",
        "title: Education and teaching memory",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, education, teaching, memory]",
        "sources: []",
        "---",
        "",
        "# Education and teaching memory",
        "",
        "> 직장인/일반인/고등학생 대상 교육강의 및 교과서/교원연수 작업을 CV처럼 읽을 수 있게 정리한 memory note.",
        "",
        f"- captured education-like traces: {len(edu_rows)}",
        f"- retained career-like records: {len(records)}",
        "",
        "## Direct teaching / training",
    ]
    direct_items = sections['teaching-delivery'][:20]
    if direct_items:
        for record in direct_items:
            lines.append(
                f"- date={record['date']} | audience={record['audience']} | role={record['role']} | event={record['event_name']} | content={record['summary']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Textbook / material development"])
    textbook_items = sections['textbook-development'][:25]
    if textbook_items:
        for record in textbook_items:
            lines.append(
                f"- date={record['date']} | audience={record['audience']} | role={record['role']} | event={record['event_name']} | content={record['summary']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Education operations / support"])
    support_items = sections['instruction-support'][:20]
    if support_items:
        for record in support_items:
            lines.append(
                f"- date={record['date']} | audience={record['audience']} | role={record['role']} | event={record['event_name']} | content={record['summary']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Audience map"])
    for audience in sorted(by_audience):
        sample = '; '.join(item['event_name'] for item in by_audience[audience][:3])
        lines.append(f"- {audience}: {len(by_audience[audience])} records — {sample}")
    lines.extend(["", "## Selected timeline"])
    for record in sections['timeline'][:24]:
        lines.append(
            f"- date={record['date']} | event={record['event_name']} | audience={record['audience']} | role={record['role']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_category_notes(config: PipelineConfig, rows: list[dict], generated_at: str) -> dict[str, Path]:
    base = config.wiki_root / CATEGORY_NOTE_DIR
    base.mkdir(parents=True, exist_ok=True)
    note_paths: dict[str, Path] = {}
    by_category: dict[str, list[dict]] = {key: [] for key in COMMON_CATEGORY_ORDER}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row)

    for category, items in by_category.items():
        if not items:
            continue
        path = base / f"{category}.md"
        lines = [
            "---",
            f"title: Jarvis intelligence category - {category}",
            f"created: {generated_at[:10]}",
            f"updated: {generated_at[:10]}",
            "type: query",
            f"tags: [jarvis, intelligence, {category}]",
            "sources: []",
            "---",
            "",
            f"# {category.title()} intelligence",
            "",
        ]
        for row in items[:30]:
            lines.append(f"- {row['sent_at']} — {row['subject']} ({row['from_addr'] or 'unknown'})")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        note_paths[category] = path
    return note_paths


def _write_intelligence_index(
    config: PipelineConfig,
    note_paths: dict[str, Path],
    generated_at: str,
    report_rel_path: str,
    *,
    priority_links: list[str] | None = None,
) -> Path:
    path = config.wiki_root / INDEX_NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "title: Jarvis intelligence index",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "tags: [jarvis, intelligence, index]",
        "sources: []",
        "---",
        "",
        "# Jarvis intelligence index",
        "",
        f"- latest daily report: [[{report_rel_path.removesuffix('.md')}]]",
    ]
    if priority_links:
        lines.extend(["", "## Priority flows"])
        for rel in priority_links:
            lines.append(f"- [[{rel.removesuffix('.md')}]]")
    lines.extend(["", "## Categories"])
    for category in sorted(note_paths):
        rel = f"{CATEGORY_NOTE_DIR}/{category}"
        lines.append(f"- [[{rel}]]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def generate_daily_intelligence_report(
    config: PipelineConfig,
    *,
    as_of: datetime | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict:
    bootstrap_workspace(config)
    moment = (as_of or _utc_now()).astimezone(UTC).replace(microsecond=0)
    rows = _load_recent_knowledge_rows(config.database_path, as_of=moment, lookback_days=lookback_days)
    rows = [row for row in rows if _should_include_in_daily_report(row)]
    by_category: dict[str, list[dict]] = {key: [] for key in COMMON_CATEGORY_ORDER}
    opportunities = _dedup_rows([row for row in rows if float(row.get("opportunity_score") or 0.0) >= 0.2], limit=10)
    for row in rows:
        by_category.setdefault(row["category"], []).append(row)
    artifact_dir = config.workspace_root / "data" / "intelligence"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    artifact_path = artifact_dir / f"daily-intelligence-{stamp}.md"
    report_rel_path = f"{INTELLIGENCE_NOTE_DIR}/daily-{moment.date().isoformat()}.md"
    wiki_path = config.wiki_root / report_rel_path
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Daily Intelligence Report — {moment.astimezone().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Lookback: last {lookback_days} days",
        "",
        "## Opportunity signals",
    ]
    if opportunities:
        for row in opportunities:
            lines.append(f"- [{row['category']}] {row['subject']} — {row['from_addr'] or 'unknown'} ({row['sent_at']})")
    else:
        lines.append("- No strong opportunity signals found in the current lookback window.")
    for category in COMMON_CATEGORY_ORDER:
        if category in {"admin", "security", "general"}:
            continue
        items = _dedup_rows(by_category.get(category) or [], limit=8)
        if not items:
            continue
        lines.extend(["", f"## {category.title()}"])
        for row in items:
            lines.append(f"- {row['subject']} — {row['from_addr'] or 'unknown'} ({row['sent_at']})")
    text = "\n".join(lines) + "\n"
    artifact_path.write_text(text, encoding="utf-8")
    wiki_path.write_text(text, encoding="utf-8")
    _systematic_backfill_message_participant_cache(config.database_path, limit=40)
    note_paths = _write_category_notes(config, rows, moment.date().isoformat())
    priority_flow_rows = _load_jongwon_smartx_flow_rows(config.database_path, as_of=moment)
    priority_flow_path = _write_jongwon_smartx_flow_note(config, priority_flow_rows, moment.date().isoformat())
    direct_actions_path = _write_jongwon_direct_actions_note(config, priority_flow_rows, moment.date().isoformat())
    smartx_weekly_path = _write_smartx_weekly_briefing_note(config, priority_flow_rows, moment.date().isoformat(), as_of=moment)
    phase_map_path = _write_jongwon_phase_map_note(config, priority_flow_rows, moment.date().isoformat())
    context_cases_path = _write_jongwon_context_cases_note(config, priority_flow_rows, moment.date().isoformat())
    chain_note_path = _write_interaction_chain_note(config, rows, moment.date().isoformat())
    advisor_action_path = _write_advisor_action_status_note(config, priority_flow_rows, moment.date().isoformat())
    project_work_items_path = _write_project_work_items_note(config, priority_flow_rows, moment.date().isoformat())
    recent_action_alerts_path = _write_recent_action_alerts_note(config, rows, moment.date().isoformat(), as_of=moment)
    next_day_mail_todos_path = _write_next_day_mail_todos_note(config, moment.date().isoformat(), as_of=moment)
    education_memory_path = _write_education_teaching_memory_note(config, rows, moment.date().isoformat())
    index_path = _write_intelligence_index(
        config,
        note_paths,
        moment.date().isoformat(),
        report_rel_path,
        priority_links=[
            JONGWON_SMARTX_FLOW_NOTE,
            JONGWON_DIRECT_ACTIONS_NOTE,
            SMARTX_WEEKLY_BRIEFING_NOTE,
            JONGWON_PHASE_MAP_NOTE,
            JONGWON_CONTEXT_CASES_NOTE,
            INTERACTION_CHAIN_NOTE,
            ADVISOR_ACTION_STATUS_NOTE,
            PROJECT_WORK_ITEMS_NOTE,
            RECENT_ACTION_ALERTS_NOTE,
            NEXT_DAY_MAIL_TODOS_NOTE,
            EDUCATION_TEACHING_MEMORY_NOTE,
        ],
    )
    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_intelligence_reports (
                report_id, generated_at, lookback_days, item_count, opportunity_count, artifact_file, wiki_note_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                moment.date().isoformat(),
                moment.isoformat(),
                lookback_days,
                len(rows),
                len(opportunities),
                artifact_path.name,
                str(wiki_path),
            ),
        )
        conn.commit()
    checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8")) if config.checkpoints_path.exists() else {}
    checkpoints.setdefault("daily_intelligence", {})
    checkpoints["daily_intelligence"]["latest"] = {
        "generated_at": moment.isoformat(),
        "artifact_file": artifact_path.name,
        "wiki_note_path": str(wiki_path),
        "item_count": len(rows),
        "opportunity_count": len(opportunities),
        "index_path": str(index_path),
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "generated_at": moment.isoformat(),
        "artifact_path": artifact_path,
        "wiki_note_path": wiki_path,
        "index_path": index_path,
        "item_count": len(rows),
        "opportunity_count": len(opportunities),
        "categories": {key: len(value) for key, value in by_category.items() if value},
    }
