from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
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
INDEX_NOTE = f"{INTELLIGENCE_NOTE_DIR}/index.md"
MONTHLY_TIMELINE_NOTE = "queries/jinwang-jarvis-monthly-timeline-36m.md"
DEFAULT_LOOKBACK_DAYS = 7
MAX_PAGES = 200
PAGE_SIZE = 100


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
            normalized = normalize_envelope(account=account, folder_kind="knowledge", folder_name=folder_name, envelope=item)
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
                    knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr,
                    sent_at, has_attachment, category, tags_json, importance_score,
                    opportunity_score, summary_text, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["message_id"],
                    row["account"],
                    row["folder_name"],
                    row["source_id"],
                    row.get("subject"),
                    row.get("from_addr"),
                    row.get("to_addr"),
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
        rows = _fetch_all_mail_rows(runner=runner, account=account, folder_name=all_mail_folder, start=start, end=end)
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
            SELECT knowledge_id, account, subject, from_addr, sent_at, category, tags_json,
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


def _write_intelligence_index(config: PipelineConfig, note_paths: dict[str, Path], generated_at: str, report_rel_path: str) -> Path:
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
        "",
        "## Categories",
    ]
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
    note_paths = _write_category_notes(config, rows, moment.date().isoformat())
    index_path = _write_intelligence_index(config, note_paths, moment.date().isoformat(), report_rel_path)
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
