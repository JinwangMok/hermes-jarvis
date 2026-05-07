from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

DEFAULT_HERMES_HOME = Path.home() / ".hermes"
DEFAULT_SKILL_SEARCH_DB = Path("state/hermes-skill-search.sqlite")
DEFAULT_SKILL_TELEMETRY_PATH = Path("state/hermes-skill-usage.json")
DEFAULT_SKILL_SEARCH_LOG_PATH = Path("state/hermes-skill-search-log.jsonl")
SCHEMA_VERSION = "1"

_TOKEN_RE = re.compile(r"[A-Za-z0-9_가-힣]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)^(?P<prefix>\s*(?:[-*]\s*)?[\w.-]*(?:api[_-]?key|apikey|token|secret|password|passwd|credential|authorization|bearer)[\w.-]*\s*[:=]\s*)(?P<value>.+)$"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL)
_LONG_SECRET_RE = re.compile(r"\b(?=[A-Za-z0-9_/-]{32,}\b)(?=[A-Za-z0-9_/-]*[A-Za-z])(?=[A-Za-z0-9_/-]*\d)[A-Za-z0-9_/-]+\b")
_NEGATIVE_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:does not|doesn't|do not|don't|cannot|can't|never)\s+work\b", re.IGNORECASE),
    re.compile(r"\b(?:unavailable|not available|not installed|missing|blocked|unsupported)\b", re.IGNORECASE),
    re.compile(r"\b(?:fails?|broken)\b", re.IGNORECASE),
    re.compile(r"\b(?:안\s*됨|작동하지\s*않|불가능|없음|미설치|막힘)\b", re.IGNORECASE),
)


class FTS5UnavailableError(RuntimeError):
    """Raised when the local sqlite3 build does not provide FTS5."""


@dataclass(frozen=True)
class SkillSearchResult:
    rank: int
    name: str
    path: str
    score: float
    bm25_rank: float
    purpose: str
    triggers: list[str]
    tags: list[str]
    related: list[str]
    pinned: bool
    archived: bool
    stale: bool
    use_count: int
    last_used_at: str | None
    negative_claim_count: int
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "name": self.name,
            "path": self.path,
            "score": self.score,
            "bm25_rank": self.bm25_rank,
            "purpose": self.purpose,
            "triggers": list(self.triggers),
            "tags": list(self.tags),
            "related": list(self.related),
            "pinned": self.pinned,
            "archived": self.archived,
            "stale": self.stale,
            "use_count": self.use_count,
            "last_used_at": self.last_used_at,
            "negative_claim_count": self.negative_claim_count,
            "snippet": self.snippet,
        }


@dataclass(frozen=True)
class SkillSearchGoldQuery:
    query: str
    expected_skill_names: list[str]


@dataclass(frozen=True)
class _ParsedSkill:
    path: Path
    root: Path
    source: str
    name: str
    purpose: str
    triggers: list[str]
    tags: list[str]
    related: list[str]
    content_redacted: str
    content_hash: str
    usage_hash: str
    metadata: dict[str, Any]
    archived: bool
    stale: bool
    pinned: bool
    use_count: int
    last_used_at: str | None
    negative_claim_count: int


def redact_obvious_secrets(text: str) -> str:
    """Redact obvious secret material before text is persisted or indexed."""
    redacted = _PRIVATE_KEY_RE.sub("[REDACTED_PRIVATE_KEY]", text)
    redacted = _BEARER_RE.sub("Bearer [REDACTED_SECRET]", redacted)
    redacted = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group('prefix')}[REDACTED_SECRET]", redacted)
    return _LONG_SECRET_RE.sub("[REDACTED_SECRET]", redacted)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_obvious_secrets(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _external_dirs_from_config(config_path: Path | None) -> list[Path]:
    if config_path is None:
        return []
    raw = _safe_load_yaml(config_path.expanduser())
    raw_skills = raw.get("skills")
    skills = raw_skills if isinstance(raw_skills, dict) else {}
    dirs = skills.get("external_dirs") or raw.get("external_dirs") or []
    if isinstance(dirs, str):
        dirs = [dirs]
    if not isinstance(dirs, list):
        return []
    return [Path(str(item)).expanduser() for item in dirs if item]


def skill_roots_from_config(
    *,
    hermes_home: Path | str = DEFAULT_HERMES_HOME,
    hermes_config_path: Path | str | None = None,
    skill_roots: Sequence[Path | str] | None = None,
) -> list[dict[str, str]]:
    if skill_roots:
        return [{"kind": "explicit", "path": str(Path(root).expanduser())} for root in skill_roots]
    hermes_home = Path(hermes_home).expanduser()
    roots = [{"kind": "builtin", "path": str(hermes_home / "skills")}]
    if hermes_config_path:
        roots.extend({"kind": "external", "path": str(path)} for path in _external_dirs_from_config(Path(hermes_config_path)))
    return roots


def _iter_skill_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("SKILL.md") if path.is_file())


def _frontmatter_and_body(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw_frontmatter = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            try:
                loaded = yaml.safe_load(raw_frontmatter) or {}
            except Exception:
                return {}, body
            return (loaded if isinstance(loaded, dict) else {}), body
    return {}, text


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts = [part.strip() for part in re.split(r"[,\n]", item) if part.strip()]
                items.extend(parts or [item.strip()])
            elif item is not None:
                items.append(str(item).strip())
        return sorted(dict.fromkeys(item for item in items if item))
    if isinstance(value, str):
        return sorted(dict.fromkeys(part.strip() for part in re.split(r"[,\n]", value) if part.strip()))
    return [str(value).strip()] if str(value).strip() else []


def _first_paragraph(body: str) -> str:
    for block in re.split(r"\n\s*\n", body):
        cleaned = " ".join(line.strip() for line in block.splitlines() if line.strip() and not line.lstrip().startswith("#"))
        if cleaned:
            return cleaned[:240]
    return ""


def _load_telemetry(path: Path | str | None) -> dict[str, Any]:
    if path is None:
        return {}
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _telemetry_key(skill_dir: Path) -> str:
    return str(skill_dir.expanduser().resolve())


def _telemetry_for_skill(skill_dir: Path, name: str, telemetry_index: dict[str, Any]) -> dict[str, Any]:
    skills = telemetry_index.get("skills") or {}
    if not isinstance(skills, dict):
        return {}
    candidates = (
        _telemetry_key(skill_dir),
        str(skill_dir),
        str(skill_dir.expanduser()),
        name,
        skill_dir.name,
    )
    for candidate in candidates:
        entry = skills.get(candidate)
        if isinstance(entry, dict):
            return entry
    resolved = _telemetry_key(skill_dir)
    for entry in skills.values():
        if not isinstance(entry, dict):
            continue
        entry_path = _string_or_none(entry.get("path"))
        entry_name = _string_or_none(entry.get("name"))
        if entry_name in {name, skill_dir.name}:
            return entry
        if entry_path:
            try:
                if str(Path(entry_path).expanduser().resolve()) == resolved:
                    return entry
            except Exception:
                if entry_path in {str(skill_dir), str(skill_dir.expanduser())}:
                    return entry
    return {}


def _read_usage(skill_dir: Path, name: str, telemetry_index: dict[str, Any] | None = None) -> dict[str, Any]:
    usage_path = skill_dir / ".usage.json"
    sidecar: dict[str, Any] = {}
    if not usage_path.exists():
        sidecar = {}
    else:
        try:
            raw = json.loads(usage_path.read_text(encoding="utf-8"))
            sidecar = raw if isinstance(raw, dict) else {"_invalid": True}
        except Exception:
            sidecar = {"_invalid": True}
    telemetry = _telemetry_for_skill(skill_dir, name, telemetry_index or {})
    if telemetry:
        merged = {**sidecar, **telemetry, "_source": "zeusos_telemetry"}
        if sidecar and not sidecar.get("_invalid"):
            merged["_source"] = "sidecar+zeusos_telemetry"
        return merged
    if sidecar:
        sidecar.setdefault("_source", "sidecar")
    return sidecar


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _negative_claim_count(text: str) -> int:
    snippets: set[str] = set()
    for pattern in _NEGATIVE_CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            snippets.add(" ".join(text[max(0, match.start() - 80) : min(len(text), match.end() + 80)].split()))
    return len(snippets)


def _parse_skill(skill_md: Path, root: Path, source: str, telemetry_index: dict[str, Any] | None = None) -> _ParsedSkill:
    raw_text = skill_md.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = _frontmatter_and_body(raw_text)
    redacted_frontmatter = _redact_value(frontmatter)
    redacted_body = redact_obvious_secrets(body)
    skill_dir = skill_md.parent
    name = _string_or_none(redacted_frontmatter.get("name")) or skill_dir.name
    purpose = (
        _string_or_none(redacted_frontmatter.get("purpose"))
        or _string_or_none(redacted_frontmatter.get("description"))
        or _string_or_none(redacted_frontmatter.get("summary"))
        or _first_paragraph(redacted_body)
    )
    triggers = _coerce_list(redacted_frontmatter.get("triggers") or redacted_frontmatter.get("trigger_phrases"))
    tags = _coerce_list(redacted_frontmatter.get("tags"))
    related = _coerce_list(redacted_frontmatter.get("related") or redacted_frontmatter.get("related_skills"))
    usage = _redact_value(_read_usage(skill_dir, name, telemetry_index))
    state = str(usage.get("state") or redacted_frontmatter.get("state") or "").lower()
    archived = bool(redacted_frontmatter.get("archived")) or state == "archived" or ".archive" in skill_dir.parts
    stale = bool(redacted_frontmatter.get("stale")) or state == "stale"
    pinned = bool(usage.get("pinned") or redacted_frontmatter.get("pinned"))
    use_count = int(usage.get("use_count") or 0) if str(usage.get("use_count") or "0").isdigit() else 0
    last_used_at = _string_or_none(usage.get("last_used_at") or usage.get("last_successful_apply_at") or usage.get("last_viewed_at"))
    content_redacted = "\n\n".join(
        part
        for part in (
            name,
            purpose,
            " ".join(triggers),
            " ".join(tags),
            " ".join(related),
            " ".join(str(part) for part in skill_dir.parts[-4:]),
            redacted_body,
        )
        if part
    )
    content_hash = hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()
    usage_hash = hashlib.sha256(json.dumps(usage, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    metadata = {
        "frontmatter": redacted_frontmatter,
        "usage": usage,
        "source": source,
        "skill_md": str(skill_md),
    }
    return _ParsedSkill(
        path=skill_dir,
        root=root,
        source=source,
        name=name,
        purpose=purpose,
        triggers=triggers,
        tags=tags,
        related=related,
        content_redacted=content_redacted,
        content_hash=content_hash,
        usage_hash=usage_hash,
        metadata=metadata,
        archived=archived,
        stale=stale,
        pinned=pinned,
        use_count=use_count,
        last_used_at=last_used_at,
        negative_claim_count=_negative_claim_count(raw_text),
    )


def _ensure_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._zeusos_fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE temp._zeusos_fts5_probe")
    except sqlite3.OperationalError as exc:
        raise FTS5UnavailableError("SQLite FTS5 extension is unavailable; Hermes skill search index cannot be built") from exc


def _initialise_schema(conn: sqlite3.Connection) -> None:
    _ensure_fts5(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS skills(
            path TEXT PRIMARY KEY,
            root TEXT NOT NULL,
            source TEXT NOT NULL,
            name TEXT NOT NULL,
            purpose TEXT NOT NULL,
            triggers_json TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            related_json TEXT NOT NULL,
            content_redacted TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            usage_hash TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            archived INTEGER NOT NULL,
            stale INTEGER NOT NULL,
            pinned INTEGER NOT NULL,
            use_count INTEGER NOT NULL,
            last_used_at TEXT,
            negative_claim_count INTEGER NOT NULL,
            indexed_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
            path UNINDEXED,
            name,
            purpose,
            triggers,
            tags,
            related,
            content,
            tokenize='unicode61'
        )
        """
    )
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (SCHEMA_VERSION,))


def _json_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False, sort_keys=True)


def _upsert_skill(conn: sqlite3.Connection, skill: _ParsedSkill, indexed_at: str) -> str:
    path = str(skill.path)
    existing = conn.execute("SELECT content_hash, usage_hash FROM skills WHERE path = ?", (path,)).fetchone()
    if existing and existing["content_hash"] == skill.content_hash and existing["usage_hash"] == skill.usage_hash:
        return "skipped"
    conn.execute(
        """
        INSERT OR REPLACE INTO skills(
            path, root, source, name, purpose, triggers_json, tags_json, related_json,
            content_redacted, content_hash, usage_hash, metadata_json, archived, stale,
            pinned, use_count, last_used_at, negative_claim_count, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            path,
            str(skill.root),
            skill.source,
            skill.name,
            skill.purpose,
            _json_list(skill.triggers),
            _json_list(skill.tags),
            _json_list(skill.related),
            skill.content_redacted,
            skill.content_hash,
            skill.usage_hash,
            json.dumps(skill.metadata, ensure_ascii=False, sort_keys=True),
            int(skill.archived),
            int(skill.stale),
            int(skill.pinned),
            skill.use_count,
            skill.last_used_at,
            skill.negative_claim_count,
            indexed_at,
        ),
    )
    conn.execute("DELETE FROM skills_fts WHERE path = ?", (path,))
    conn.execute(
        "INSERT INTO skills_fts(path, name, purpose, triggers, tags, related, content) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (path, skill.name, skill.purpose, " ".join(skill.triggers), " ".join(skill.tags), " ".join(skill.related), skill.content_redacted),
    )
    return "updated" if existing else "inserted"


def build_skill_search_index(
    db_path: Path | str,
    *,
    hermes_home: Path | str = DEFAULT_HERMES_HOME,
    hermes_config_path: Path | str | None = None,
    skill_roots: Sequence[Path | str] | None = None,
    telemetry_path: Path | str | None = DEFAULT_SKILL_TELEMETRY_PATH,
) -> dict[str, Any]:
    db_path = Path(db_path).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    roots = skill_roots_from_config(hermes_home=hermes_home, hermes_config_path=hermes_config_path, skill_roots=skill_roots)
    telemetry_index = _load_telemetry(telemetry_path)
    indexed_at = datetime.now(timezone.utc).isoformat()
    counts = {"inserted": 0, "updated": 0, "skipped": 0, "deleted": 0, "errors": 0}
    seen_paths: set[str] = set()
    errors: list[dict[str, str]] = []
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            _initialise_schema(conn)
            for root in roots:
                root_path = Path(root["path"]).expanduser()
                for skill_md in _iter_skill_files(root_path):
                    try:
                        parsed = _parse_skill(skill_md, root_path, root["kind"], telemetry_index)
                        status = _upsert_skill(conn, parsed, indexed_at)
                        counts[status] += 1
                        seen_paths.add(str(parsed.path))
                    except Exception as exc:  # pragma: no cover - defensive per-skill isolation
                        counts["errors"] += 1
                        errors.append({"path": str(skill_md), "error": str(exc)})
            existing_paths = [row["path"] for row in conn.execute("SELECT path FROM skills").fetchall()]
            for path in existing_paths:
                if path not in seen_paths:
                    conn.execute("DELETE FROM skills WHERE path = ?", (path,))
                    conn.execute("DELETE FROM skills_fts WHERE path = ?", (path,))
                    counts["deleted"] += 1
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('indexed_at', ?)", (indexed_at,))
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('roots', ?)", (json.dumps(roots, ensure_ascii=False, sort_keys=True),))
            conn.commit()
    except FTS5UnavailableError as exc:
        return {"ok": False, "reason": "fts5_unavailable", "database_path": str(db_path), "error": str(exc), "roots": roots}
    except sqlite3.Error as exc:
        return {"ok": False, "reason": "sqlite_error", "database_path": str(db_path), "error": str(exc), "roots": roots}
    return {
        "ok": True,
        "database_path": str(db_path),
        "indexed_at": indexed_at,
        "roots": roots,
        "telemetry_path": str(Path(telemetry_path).expanduser()) if telemetry_path else None,
        "counts": counts,
        "errors": errors,
    }


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def _fts_query(query: str) -> str:
    terms = sorted(dict.fromkeys(_tokens(query)))
    return " OR ".join(f'"{term}"' for term in terms)


def _load_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _overlap(terms: set[str], values: Sequence[str]) -> int:
    value_terms: set[str] = set()
    for value in values:
        value_terms.update(_tokens(value))
    return len(terms & value_terms)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recency_boost(last_used_at: str | None, now: datetime) -> float:
    parsed = _parse_datetime(last_used_at)
    if parsed is None:
        return 0.0
    age_days = max(0, (now - parsed).days)
    if age_days <= 7:
        return 3.0
    if age_days <= 30:
        return 2.0
    if age_days <= 90:
        return 1.0
    return 0.25


def _snippet(text: str, terms: set[str], max_chars: int = 420) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    lower = collapsed.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    start = max(0, min(positions) - 90) if positions else 0
    end = min(len(collapsed), start + max_chars)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(collapsed) else ""
    return f"{prefix}{collapsed[start:end]}{suffix}"


def _score_row(row: sqlite3.Row, terms: set[str], now: datetime) -> tuple[float, SkillSearchResult]:
    triggers = _load_json_list(row["triggers_json"])
    tags = _load_json_list(row["tags_json"])
    related = _load_json_list(row["related_json"])
    bm25_rank = float(row["rank"])
    base_score = -bm25_rank if bm25_rank < 0 else 1.0 / (1.0 + bm25_rank)
    name_terms = set(_tokens(row["name"]))
    path_terms = set(_tokens(Path(row["path"]).name)) | set(_tokens(row["path"]))
    purpose_terms = set(_tokens(row["purpose"]))
    score = base_score
    exact_name_overlap = len(terms & name_terms)
    score += exact_name_overlap * 10.0
    score += len(terms & path_terms) * 3.0
    query_text = " ".join(sorted(terms))
    name_text = row["name"].lower()
    path_name_text = Path(row["path"]).name.lower()
    if name_text in query_text or query_text in name_text or path_name_text in query_text or query_text in path_name_text:
        score += 8.0
    score += len(terms & purpose_terms) * 2.0
    score += _overlap(terms, triggers) * 5.0
    score += _overlap(terms, tags) * 4.0
    score += _overlap(terms, related) * 2.5
    score += min(3.0, math.log1p(int(row["use_count"] or 0)) * 0.75)
    score += min(3.0, _recency_boost(row["last_used_at"], now))
    if row["pinned"]:
        score += 10.0
    if row["stale"]:
        score -= 3.0
    if row["archived"]:
        score -= 25.0
    score -= min(20.0, float(row["negative_claim_count"] or 0) * 6.0)
    result = SkillSearchResult(
        rank=0,
        name=row["name"],
        path=row["path"],
        score=round(score, 6),
        bm25_rank=round(bm25_rank, 6),
        purpose=row["purpose"],
        triggers=triggers,
        tags=tags,
        related=related,
        pinned=bool(row["pinned"]),
        archived=bool(row["archived"]),
        stale=bool(row["stale"]),
        use_count=int(row["use_count"] or 0),
        last_used_at=row["last_used_at"],
        negative_claim_count=int(row["negative_claim_count"] or 0),
        snippet=_snippet(row["content_redacted"], terms),
    )
    return score, result


def log_skill_search(
    log_path: Path | str,
    *,
    query: str,
    top_k: int,
    returned_skill_names: Sequence[str],
    selected_skill: str | None = None,
    clicked_skill: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    path = Path(log_path).expanduser()
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    event = {
        "timestamp": timestamp,
        "query": query,
        "top_k": int(top_k),
        "returned_skill_names": [str(name) for name in returned_skill_names],
    }
    if selected_skill:
        event["selected_skill"] = str(selected_skill)
    if clicked_skill:
        event["clicked_skill"] = str(clicked_skill)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return {"ok": True, "log_path": str(path), "event": event}


def _load_gold_queries(path: Path | str) -> list[SkillSearchGoldQuery]:
    path = Path(path).expanduser()
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("queries") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("gold query fixture must be a list or an object with a queries list")
    queries: list[SkillSearchGoldQuery] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        query = _string_or_none(item.get("query"))
        expected = item.get("expected_skill_names") or item.get("expected") or []
        expected_names = [str(name) for name in expected if str(name).strip()] if isinstance(expected, list) else []
        if query and expected_names:
            queries.append(SkillSearchGoldQuery(query=query, expected_skill_names=expected_names))
    return queries


def _recall_at_k(actual: Sequence[str], expected: Sequence[str], k: int) -> float:
    expected_set = set(expected)
    if not expected_set:
        return 0.0
    return len(set(actual[:k]) & expected_set) / len(expected_set)


def _mrr_at_k(actual: Sequence[str], expected: Sequence[str], k: int) -> float:
    expected_set = set(expected)
    if not expected_set:
        return 0.0
    for index, name in enumerate(actual[:k], start=1):
        if name in expected_set:
            return 1.0 / index
    return 0.0


def evaluate_skill_search(
    db_path: Path | str,
    gold_queries: Sequence[SkillSearchGoldQuery | dict[str, Any]] | Path | str,
    *,
    k: int = 5,
    include_archived: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    if isinstance(gold_queries, (str, Path)):
        queries = _load_gold_queries(gold_queries)
        fixture_path = str(Path(gold_queries).expanduser())
    else:
        queries = []
        fixture_path = None
        for item in gold_queries:
            if isinstance(item, SkillSearchGoldQuery):
                queries.append(item)
            elif isinstance(item, dict):
                expected = item.get("expected_skill_names") or item.get("expected") or []
                expected_names = [str(name) for name in expected if str(name).strip()] if isinstance(expected, list) else []
                query = _string_or_none(item.get("query"))
                if query and expected_names:
                    queries.append(SkillSearchGoldQuery(query=query, expected_skill_names=expected_names))
    bounded_k = max(1, min(int(k), 100))
    rows: list[dict[str, Any]] = []
    for gold in queries:
        result = search_skills(db_path, gold.query, top_k=bounded_k, include_archived=include_archived, now=now)
        actual = [str(row["name"]) for row in result.get("rows", [])]
        recall = _recall_at_k(actual, gold.expected_skill_names, bounded_k)
        mrr = _mrr_at_k(actual, gold.expected_skill_names, bounded_k)
        rows.append({
            "query": gold.query,
            "expected_skill_names": list(gold.expected_skill_names),
            "returned_skill_names": actual,
            "recall_at_k": round(recall, 6),
            "mrr_at_k": round(mrr, 6),
            "ok": bool(result.get("ok")),
            "reason": result.get("reason"),
        })
    count = len(rows)
    recall_mean = sum(row["recall_at_k"] for row in rows) / count if count else 0.0
    mrr_mean = sum(row["mrr_at_k"] for row in rows) / count if count else 0.0
    return {
        "ok": True,
        "database_path": str(Path(db_path).expanduser()),
        "gold_path": fixture_path,
        "k": bounded_k,
        "query_count": count,
        "recall_at_k": round(recall_mean, 6),
        "mrr_at_k": round(mrr_mean, 6),
        "rows": rows,
    }


def search_skills(
    db_path: Path | str,
    query: str,
    top_k: int = 5,
    include_archived: bool = False,
    *,
    now: datetime | None = None,
    search_log_path: Path | str | None = None,
    selected_skill: str | None = None,
    clicked_skill: str | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path).expanduser()
    normalized_query = query.strip()
    bounded_top_k = max(1, min(int(top_k), 100))
    if not normalized_query:
        return {"ok": False, "reason": "empty_query", "database_path": str(db_path), "query": query, "rows": []}
    match_query = _fts_query(normalized_query)
    if not match_query:
        return {"ok": False, "reason": "empty_query", "database_path": str(db_path), "query": query, "rows": []}
    if not db_path.exists():
        return {"ok": False, "reason": "index_missing", "database_path": str(db_path), "query": normalized_query, "rows": []}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    archive_clause = "" if include_archived else "AND skills.archived = 0"
    limit = max(250, bounded_top_k * 20)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT skills.*, bm25(skills_fts, 0.0, 5.0, 3.0, 4.0, 4.0, 2.0, 1.0) AS rank
                FROM skills_fts
                JOIN skills ON skills_fts.path = skills.path
                WHERE skills_fts MATCH ? {archive_clause}
                LIMIT ?
                """,
                (match_query, limit),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        return {"ok": False, "reason": "sqlite_fts_error", "database_path": str(db_path), "query": normalized_query, "error": str(exc), "rows": []}
    except sqlite3.Error as exc:
        return {"ok": False, "reason": "sqlite_error", "database_path": str(db_path), "query": normalized_query, "error": str(exc), "rows": []}

    query_terms = set(_tokens(normalized_query))
    scored = [_score_row(row, query_terms, now) for row in rows]
    scored.sort(key=lambda item: (-item[0], item[1].name.lower(), item[1].path))
    ranked: list[dict[str, Any]] = []
    for rank, (_, result) in enumerate(scored[:bounded_top_k], start=1):
        row = result.to_dict()
        row["rank"] = rank
        ranked.append(row)
    if search_log_path is not None:
        log_skill_search(
            search_log_path,
            query=normalized_query,
            top_k=bounded_top_k,
            returned_skill_names=[str(row["name"]) for row in ranked],
            selected_skill=selected_skill,
            clicked_skill=clicked_skill,
            now=now,
        )
    return {
        "ok": True,
        "database_path": str(db_path),
        "query": normalized_query,
        "top_k": bounded_top_k,
        "include_archived": bool(include_archived),
        "rows": ranked,
    }
