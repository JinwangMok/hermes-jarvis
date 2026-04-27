from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .bootstrap import bootstrap_workspace
from .briefing import generate_briefing
from .config import PipelineConfig
from .wiki_contract import run_wiki_lint_if_available, wiki_governance, wiki_operational_source

WATCHLIST_NOTE_RELATIVE_PATH = "queries/jinwang-jarvis-importance-shift-watchlist.md"
WATCHLIST_INDEX_LINE = "- [[jinwang-jarvis-importance-shift-watchlist]] — Rolling watchlist of suppressed-but-promotable mail threads and the current importance-shift patterns in Jinwang Jarvis."
SENT_MAIL_MEMORY_INDEX_LINE = "- [[queries/jinwang-jarvis-memory/sent-mail-memory|Jinwang Jarvis Sent Mail Memory]] — 보낸편지함 메일을 신규 수신 추천에서는 제외하되, 실제 발신·회신·공유·결정 맥락을 계층적으로 저장하는 generated memory shard."
MEMORY_NOTE_DIR = "queries/jinwang-jarvis-memory"
MEMORY_INDEX_RELATIVE_PATH = f"{MEMORY_NOTE_DIR}/index.md"
MEMORY_SECTION_FILES = {
    "recent_important": f"{MEMORY_NOTE_DIR}/recent-important.md",
    "continuing_important": f"{MEMORY_NOTE_DIR}/continuing-important.md",
    "newly_important": f"{MEMORY_NOTE_DIR}/newly-important.md",
    "schedule_recommendations": f"{MEMORY_NOTE_DIR}/schedule-recommendations.md",
    "sent_mail_memory": f"{MEMORY_NOTE_DIR}/sent-mail-memory.md",
}


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _load_checkpoints(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_checkpoints(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_latest_proposal_payload(config: PipelineConfig) -> tuple[dict, Path]:
    checkpoints = _load_checkpoints(config.checkpoints_path)
    latest = ((checkpoints.get("proposals") or {}).get("latest") or {})
    artifact_file = latest.get("artifact_file")
    if not artifact_file:
        raise FileNotFoundError("No latest proposal artifact recorded in checkpoints")
    artifact_path = config.workspace_root / "data" / "proposals" / artifact_file
    if not artifact_path.exists():
        raise FileNotFoundError(f"Latest proposal artifact not found: {artifact_path}")
    return json.loads(artifact_path.read_text(encoding="utf-8")), artifact_path


def _promotion_score(details: dict) -> float:
    scores = details.get("scores") or {}
    priority = float(scores.get("priority", 0.0))
    action = float(scores.get("action", 0.0))
    calendar = float(scores.get("calendar", 0.0))
    noise = float(scores.get("noise", 0.0))
    date_confidence = float(scores.get("date_confidence", 0.0))
    signal_confidence = float(scores.get("signal_confidence", 0.0))
    value = priority * 0.34 + action * 0.22 + calendar * 0.18 + date_confidence * 0.16 + signal_confidence * 0.18 - noise * 0.18
    return max(0.0, min(value, 1.0))


def _watch_kind(entry: dict) -> str:
    details = entry.get("details") or {}
    scores = details.get("scores") or {}
    labels = set(details.get("labels") or [])
    signal_confidence = float(scores.get("signal_confidence", 0.0))
    if signal_confidence >= 0.9:
        return "reply-backed-candidate"
    if "advisor-fyi" in labels:
        return "advisor-fyi-revival"
    return "promotion-candidate"


def _should_watch(entry: dict) -> bool:
    details = entry.get("details") or {}
    if not details:
        return False
    scores = details.get("scores") or {}
    labels = set(details.get("labels") or [])
    suppression = details.get("suppression") or {}
    suppression_kind = suppression.get("kind") or (entry.get("reason") or {}).get("kind")
    promotion_score = _promotion_score(details)
    signal_confidence = float(scores.get("signal_confidence", 0.0))
    date_confidence = float(scores.get("date_confidence", 0.0))
    action = float(scores.get("action", 0.0))
    if suppression_kind in {"feedback-dedup-key", "feedback-summary-match", "policy-past-event"}:
        return False
    if suppression_kind == "policy-promotional-subject" and signal_confidence < 0.9 and "advisor-fyi" not in labels:
        return False
    return (
        promotion_score >= 0.48
        or signal_confidence >= 0.9
        or "advisor-fyi" in labels
        or (date_confidence >= 0.6 and action >= 0.3)
    )


def _build_watchlist_entries(proposal_payload: dict) -> list[dict]:
    entries: list[dict] = []
    for item in proposal_payload.get("suppressed", []):
        details = item.get("details") or {}
        if not _should_watch(item):
            continue
        entries.append(
            {
                "source_message_id": item.get("source_message_id"),
                "title": item.get("title") or "Untitled",
                "watch_kind": _watch_kind(item),
                "promotion_score": _promotion_score(details),
                "reason": item.get("reason") or {},
                "details": details,
            }
        )
    entries.sort(key=lambda row: (-float(row["promotion_score"]), row["source_message_id"] or ""))
    return entries[:12]


def _upsert_watchlist(conn: sqlite3.Connection, entries: list[dict], generated_at: str, artifact_file: str, wiki_note_path: str | None) -> None:
    for entry in entries:
        existing = conn.execute(
            "SELECT first_seen_at, seen_count FROM message_watchlist WHERE source_message_id = ?",
            (entry["source_message_id"],),
        ).fetchone()
        first_seen_at = existing[0] if existing else generated_at
        seen_count = int(existing[1]) + 1 if existing else 1
        conn.execute(
            """
            INSERT INTO message_watchlist (
                source_message_id, title, watch_kind, promotion_score, first_seen_at,
                last_seen_at, seen_count, latest_reason_json, latest_artifact_file, wiki_note_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_message_id) DO UPDATE SET
                title = excluded.title,
                watch_kind = excluded.watch_kind,
                promotion_score = excluded.promotion_score,
                last_seen_at = excluded.last_seen_at,
                seen_count = excluded.seen_count,
                latest_reason_json = excluded.latest_reason_json,
                latest_artifact_file = excluded.latest_artifact_file,
                wiki_note_path = excluded.wiki_note_path
            """,
            (
                entry["source_message_id"],
                entry["title"],
                entry["watch_kind"],
                entry["promotion_score"],
                first_seen_at,
                generated_at,
                seen_count,
                json.dumps({"reason": entry["reason"], "details": entry["details"]}, ensure_ascii=False),
                artifact_file,
                wiki_note_path,
            ),
        )


def _write_watchlist_artifact(config: PipelineConfig, entries: list[dict], proposal_payload: dict, generated_at: str) -> Path:
    watchlist_dir = config.workspace_root / "data" / "watchlists"
    watchlist_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")
    artifact_path = watchlist_dir / f"watchlist-{timestamp}.json"
    artifact_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "proposal_generated_at": proposal_payload.get("generated_at"),
                "proposal_count": proposal_payload.get("proposal_count", 0),
                "suppressed_count": proposal_payload.get("suppressed_count", 0),
                "watchlist_count": len(entries),
                "watchlist": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return artifact_path


def _update_index(index_path: Path, today: str) -> None:
    text = index_path.read_text(encoding="utf-8") if index_path.exists() else "# Wiki Index\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n"
    for index_line in (WATCHLIST_INDEX_LINE, SENT_MAIL_MEMORY_INDEX_LINE):
        if index_line in text:
            continue
        marker = "## Queries\n"
        if marker in text:
            text = text.replace(marker, marker + index_line + "\n")
        else:
            text += "\n## Queries\n" + index_line + "\n"
    pages = 0
    for section in ("entities", "concepts", "comparisons", "queries"):
        section_dir = index_path.parent / section
        if section_dir.exists():
            pages += len(list(section_dir.glob("*.md")))
    lines = []
    for line in text.splitlines():
        if line.startswith("> Last updated:"):
            lines.append(f"> Last updated: {today} | Total pages: {pages}")
        else:
            lines.append(line)
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _append_log(log_path: Path, today: str, wiki_rel_path: str, watchlist_count: int, artifact_name: str) -> None:
    wiki_root = log_path.parent
    runs_dir = wiki_root / "_meta" / "runs" / today
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_path = runs_dir / f"jarvis-watchlist-{artifact_name.replace('watchlist-', '').replace('.json', '')}.json"
    run_path.write_text(
        json.dumps(
            {
                "kind": "jarvis-watchlist-refresh",
                "date": today,
                "wiki_rel_path": wiki_rel_path,
                "watchlist_count": watchlist_count,
                "artifact": f"data/watchlists/{artifact_name}",
                "authority": "derived",
                "generated": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    marker = f"## [{today}] update | Jinwang Jarvis recurring watchlist rollup"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Wiki Log\n"
    if marker in existing:
        return
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n{marker}\n"
            f"- Refreshed `{wiki_rel_path}` as a derived generated view.\n"
            f"- Detailed per-run metadata is stored under `_meta/runs/{today}/`.\n"
            f"- Latest source artifact at first rollup: `data/watchlists/{artifact_name}`.\n"
        )


def _write_wiki_summary(config: PipelineConfig, proposal_payload: dict, entries: list[dict], generated_at: str) -> Path:
    note_path = config.wiki_root / WATCHLIST_NOTE_RELATIVE_PATH
    note_path.parent.mkdir(parents=True, exist_ok=True)
    today = generated_at[:10]
    proposals = proposal_payload.get("proposals") or []
    lines = [
        "---",
        "title: Jinwang Jarvis Importance Shift Watchlist",
        f"created: {today}",
        f"updated: {today}",
        "type: query",
        "subtype: generated-watchlist",
        "tags: [email, advisor, lab, filtering, automation, query]",
        "sources: []",
        "owner: jarvis",
        "authority: derived",
        "generated: true",
        "generator: jinwang-jarvis",
        "refresh_policy: overwrite",
        f"operational_source_of_truth: {wiki_operational_source(config)}",
        "summary: Rolling derived watchlist of suppressed-but-promotable mail threads.",
        "---",
        "",
        "# Jinwang Jarvis Importance Shift Watchlist",
        "",
        "## Why this page exists",
        "Suppressed mail can become important later as deadlines approach, more replies accumulate, or older backfill windows reveal recurring workstreams.",
        "This page keeps a rolling synthesis of threads that are currently suppressed but still look promotable.",
        "",
        "## Current active proposals",
    ]
    if proposals:
        for proposal in proposals[:8]:
            lines.append(f"- `{proposal.get('source_message_id', 'n/a')}` {proposal.get('title', 'Untitled')} — start: {proposal.get('start_ts') or 'n/a'}")
    else:
        lines.append("- No active proposals in the latest proposal artifact.")

    lines.extend(["", "## Promotion candidates"])
    if entries:
        for entry in entries:
            labels = ", ".join((entry.get("details") or {}).get("labels") or []) or "n/a"
            reason_kind = (entry.get("reason") or {}).get("kind", "unknown")
            lines.append(
                f"- `{entry['source_message_id']}` [{entry['watch_kind']}] {entry['title']} — promotion_score={entry['promotion_score']:.2f}, labels={labels}, suppression={reason_kind}"
            )
    else:
        lines.append("- No current promotion candidates.")

    lines.extend([
        "",
        "## Current pattern summary",
        f"- latest proposal artifact generated_at: {proposal_payload.get('generated_at', 'n/a')}",
        f"- active proposal count: {proposal_payload.get('proposal_count', 0)}",
        f"- suppressed candidate count: {proposal_payload.get('suppressed_count', 0)}",
        f"- watchlist candidate count: {len(entries)}",
        "- operational source of truth remains SQLite + artifacts; this page is the rolling synthesis layer.",
        "",
        "## Relationships",
        "- [[entities/jinwang-jarvis]]",
        "- [[queries/personal-intelligence-pipeline-mvp-implementation-plan-april-2026]]",
        "- [[queries/jinwang-jarvis-mvp-completion-april-2026]]",
        "- [[queries/jinwang-jarvis-memory/index]]",
    ])
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _update_index(config.wiki_root / "index.md", today)
    _append_log(config.wiki_root / "log.md", today, WATCHLIST_NOTE_RELATIVE_PATH, len(entries), f"watchlist-{datetime.fromisoformat(generated_at.replace('Z', '+00:00')).strftime('%Y%m%dT%H%M%SZ')}.json")
    return note_path


def _memory_note_title(stem: str) -> str:
    mapping = {
        "recent-important": "Jinwang Jarvis Recent Important Mail",
        "continuing-important": "Jinwang Jarvis Continuing Important Work",
        "newly-important": "Jinwang Jarvis Newly Important Work",
        "schedule-recommendations": "Jinwang Jarvis Schedule Recommendations",
        "sent-mail-memory": "Jinwang Jarvis Sent Mail Memory",
    }
    return mapping.get(stem, stem.replace("-", " ").title())


def _sent_mail_theme(subject: str | None, interaction_role: str | None) -> str:
    text = (subject or "").casefold()
    role = (interaction_role or "").casefold()
    if role in {"status-reply", "review-reply"} or text.startswith("re:"):
        return "replies-and-followups"
    if any(term in text for term in ["fw:", "fwd:", "공유", "announce", "info", "전달"]):
        return "shared-context"
    if any(term in text for term in ["참석", "일정", "meeting", "세미나", "workshop", "등록", "registration"]):
        return "events-and-scheduling"
    if any(term in text for term in ["요청", "확인", "검토", "proposal", "draft", "보고"]):
        return "requests-and-decisions"
    if any(term in text for term in ["github", "security", "login", "account", "인증", "보안"]):
        return "admin-and-security"
    return "other-sent-context"


def _load_sent_mail_memory_items(config: PipelineConfig, *, limit: int | None = None) -> list[dict]:
    query = """
            SELECT message_id, account, subject, from_addr, to_addrs, cc_addrs,
                   sent_at, snippet, self_role, interaction_role
            FROM messages
            WHERE folder_kind = 'sent'
            ORDER BY datetime(COALESCE(sent_at, '')) DESC, message_id DESC
            """
    params: tuple[int, ...] = ()
    if limit is not None:
        query += "\n            LIMIT ?"
        params = (limit,)
    with sqlite3.connect(config.database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    items: list[dict] = []
    for row in rows:
        item = dict(row)
        for key in ("to_addrs", "cc_addrs"):
            try:
                item[key] = json.loads(item.get(key) or "[]")
            except Exception:
                item[key] = []
        item["theme"] = _sent_mail_theme(item.get("subject"), item.get("interaction_role"))
        items.append(item)
    return items


def _write_sent_mail_memory_note(note_path: Path, *, config: PipelineConfig, generated_at: str, items: list[dict]) -> None:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    title = _memory_note_title(note_path.stem)
    lines = [
        "---",
        f"title: {title}",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "subtype: generated-memory-shard",
        "tags: [email, automation, memory, query]",
        "sources: []",
        "owner: jarvis",
        "authority: derived",
        "generated: true",
        "generator: jinwang-jarvis",
        "refresh_policy: overwrite",
        f"operational_source_of_truth: {wiki_operational_source(config)}",
        "---",
        "",
        "# 내가 보낸 메일 기억",
        "",
        "> 보낸편지함은 신규/중요 수신 메일 추천에는 쓰지 않고, 내가 실제로 처리·공유·결정한 맥락을 위키 장기기억으로 보존한다.",
        "",
        f"- stored_sent_items: {len(items)}",
        "",
        "## 계층",
        "- replies-and-followups: 내가 회신/상태 업데이트로 닫거나 이어간 일",
        "- shared-context: 내가 연구실/팀에 전달·공유한 정보",
        "- events-and-scheduling: 참석·등록·일정 관련 발신",
        "- requests-and-decisions: 요청·검토·결정·보고 흐름",
        "- admin-and-security: 계정·보안·운영성 발신",
        "- other-sent-context: 위 범주 밖의 발신 맥락",
        "",
    ]
    by_theme: dict[str, list[dict]] = {}
    for item in items:
        by_theme.setdefault(item["theme"], []).append(item)
    for theme in ["replies-and-followups", "shared-context", "events-and-scheduling", "requests-and-decisions", "admin-and-security", "other-sent-context"]:
        lines.extend([f"## {theme}"])
        theme_items = by_theme.get(theme, [])
        if not theme_items:
            lines.append("- none")
        for item in theme_items:
            recipients = ", ".join(item.get("to_addrs") or []) or "unknown"
            subject = item.get("subject") or "(제목 없음)"
            snippet = (item.get("snippet") or "").strip().replace("\n", " ")
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            detail = f" — key: {snippet}" if snippet else ""
            lines.append(
                f"- {item.get('sent_at') or 'unknown'} — {subject} | to={recipients} | source={item.get('message_id')}{detail}"
            )
        lines.append("")
    note_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_memory_section(note_path: Path, *, config: PipelineConfig, generated_at: str, heading: str, items: list[dict], empty_message: str) -> None:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    title = _memory_note_title(note_path.stem)
    lines = [
        "---",
        f"title: {title}",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "subtype: generated-memory-shard",
        "tags: [email, automation, memory, query]",
        "sources: []",
        "owner: jarvis",
        "authority: derived",
        "generated: true",
        "generator: jinwang-jarvis",
        "refresh_policy: overwrite",
        f"operational_source_of_truth: {wiki_operational_source(config)}",
        "---",
        "",
        f"# {heading}",
        "",
    ]
    if items:
        for item in items:
            lines.append(
                f"- {item.get('title', 'Untitled')} — source: {item.get('source_message_id', 'n/a')}, start: {item.get('start_ts') or 'n/a'}, confidence: {float(item.get('confidence') or 0.0):.2f}"
            )
    else:
        lines.append(f"- {empty_message}")
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_memory_notes(config: PipelineConfig, briefing_payload: dict, generated_at: str) -> dict[str, Path]:
    note_paths: dict[str, Path] = {}
    sent_mail_items = _load_sent_mail_memory_items(config)
    for section_name, relative_path in MEMORY_SECTION_FILES.items():
        note_path = config.wiki_root / relative_path
        if section_name == "sent_mail_memory":
            _write_sent_mail_memory_note(note_path, config=config, generated_at=generated_at, items=sent_mail_items)
            note_paths[section_name] = note_path
            continue
        heading = {
            "recent_important": "최근 중요한 일",
            "continuing_important": "계속 중요한 일",
            "newly_important": "새로 중요해진 일",
            "schedule_recommendations": "추천 일정",
        }[section_name]
        empty_message = {
            "recent_important": "현재 최근 중요 항목이 없습니다.",
            "continuing_important": "현재 계속 중요한 항목이 없습니다.",
            "newly_important": "현재 새로 중요해진 항목이 없습니다.",
            "schedule_recommendations": "현재 추천 일정이 없습니다.",
        }[section_name]
        _write_memory_section(
            note_path,
            config=config,
            generated_at=generated_at,
            heading=heading,
            items=briefing_payload.get("sections", {}).get(section_name, []),
            empty_message=empty_message,
        )
        note_paths[section_name] = note_path

    index_path = config.wiki_root / MEMORY_INDEX_RELATIVE_PATH
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_lines = [
        "---",
        "title: Jinwang Jarvis Memory Index",
        f"created: {generated_at[:10]}",
        f"updated: {generated_at[:10]}",
        "type: query",
        "subtype: generated-memory-shard",
        "tags: [email, automation, memory, query]",
        "sources: []",
        "owner: jarvis",
        "authority: derived",
        "generated: true",
        "generator: jinwang-jarvis",
        "refresh_policy: overwrite",
        f"operational_source_of_truth: {wiki_operational_source(config)}",
        "---",
        "",
        "# Jinwang Jarvis Memory Index",
        "",
        "이 메모 묶음은 최근/지속/신규 중요 메일과 추천 일정 후보를 계층적으로 저장해, 이후 대화에서 빠르게 탐색하기 위한 장기 기억 레이어다.",
        "",
        "## Sections",
        "- [[queries/jinwang-jarvis-memory/recent-important]]",
        "- [[queries/jinwang-jarvis-memory/continuing-important]]",
        "- [[queries/jinwang-jarvis-memory/newly-important]]",
        "- [[queries/jinwang-jarvis-memory/schedule-recommendations]]",
        "- [[queries/jinwang-jarvis-memory/sent-mail-memory]]",
        "- [[queries/jinwang-jarvis-importance-shift-watchlist]]",
    ]
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    note_paths["index"] = index_path
    return note_paths


def synthesize_knowledge(config: PipelineConfig, *, write_wiki: bool = True, as_of: datetime | None = None) -> dict:
    bootstrap_workspace(config)
    governance = wiki_governance(config.wiki_root)
    generated_at = (as_of or _utc_now()).isoformat().replace("+00:00", "Z")
    proposal_payload, proposal_artifact_path = _load_latest_proposal_payload(config)
    entries = _build_watchlist_entries(proposal_payload)
    artifact_path = _write_watchlist_artifact(config, entries, proposal_payload, generated_at)
    wiki_page_path = _write_wiki_summary(config, proposal_payload, entries, generated_at) if write_wiki else None
    memory_note_paths: dict[str, Path] = {}
    if write_wiki:
        briefing_result = generate_briefing(config, as_of=datetime.fromisoformat(generated_at.replace("Z", "+00:00")))
        briefing_payload = json.loads(briefing_result["artifact_path"].read_text(encoding="utf-8"))
        memory_note_paths = _write_memory_notes(config, briefing_payload, generated_at)
    with sqlite3.connect(config.database_path) as conn:
        _upsert_watchlist(conn, entries, generated_at, artifact_path.name, str(wiki_page_path) if wiki_page_path else None)
        conn.commit()
    checkpoints = _load_checkpoints(config.checkpoints_path)
    checkpoints.setdefault("knowledge", {})
    checkpoints["knowledge"]["latest"] = {
        "generated_at": generated_at,
        "artifact_file": artifact_path.name,
        "watchlist_count": len(entries),
        "wiki_page": str(wiki_page_path) if wiki_page_path else None,
        "memory_index_page": str(memory_note_paths.get("index")) if memory_note_paths.get("index") else None,
        "proposal_artifact_file": proposal_artifact_path.name,
    }
    _save_checkpoints(config.checkpoints_path, checkpoints)
    wiki_lint = run_wiki_lint_if_available(config.wiki_root) if write_wiki else None
    return {
        "generated_at": generated_at,
        "artifact_path": artifact_path,
        "watchlist_count": len(entries),
        "wiki_page_path": wiki_page_path,
        "memory_note_paths": memory_note_paths,
        "proposal_artifact_path": proposal_artifact_path,
        "wiki_governance": governance.policy_summary(),
        "wiki_lint": wiki_lint,
    }