from __future__ import annotations

import re
from pathlib import Path

GENERATED_PREFIXES = ("reports/", "queries/jinwang-jarvis-", "queries/external-hot-issues/")
DURABLE_PREFIXES = ("entities/", "concepts/", "comparisons/")
GENERATED_REQUIRED_KEYS = ("generated", "authority", "refresh_policy", "operational_source_of_truth")
CANONICAL_PHRASES_RE = re.compile(r"source of truth|canonical|확정 사실", re.IGNORECASE)
DISCLAIMER_RE = re.compile(r"derived|advisory|status|evidence|not canonical|검증|출처", re.IGNORECASE)
ACTIONABLE_RE = re.compile(r"신청 가능|apply now|actionable", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)\]]+")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}\b|deadline|due|마감|까지", re.IGNORECASE)
STRONG_CLAIM_RE = re.compile(r"\b(must|always)\b|확정|현재|source of truth", re.IGNORECASE)


def _parse_scalar(value: str) -> object:
    stripped = value.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip('"\'') for part in inner.split(",")]
    return stripped.strip('"\'')


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    frontmatter: dict[str, object] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = _parse_scalar(value)
    return frontmatter, text[end + len("\n---") :].lstrip("\n")


def _rel_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _issue(severity: str, path: str, code: str, message: str, evidence: str) -> dict[str, str]:
    return {"severity": severity, "path": path, "code": code, "message": message, "evidence": evidence}


def _is_generated_path(rel_path: str) -> bool:
    return rel_path.startswith(GENERATED_PREFIXES)


def _is_durable_path(rel_path: str) -> bool:
    if rel_path.startswith(DURABLE_PREFIXES):
        return True
    return rel_path.startswith("queries/") and not rel_path.startswith(("queries/jinwang-jarvis-", "queries/external-hot-issues/"))


def _has_non_homepage_url(text: str) -> bool:
    for url in URL_RE.findall(text):
        without_scheme = url.split("://", 1)[1].rstrip("/.,")
        if "/" in without_scheme:
            return True
    return False


def _nearby_disclaimer(text: str, match: re.Match[str]) -> bool:
    start = max(0, match.start() - 180)
    end = min(len(text), match.end() + 180)
    return bool(DISCLAIMER_RE.search(text[start:end]))


def lint_wiki_semantics(wiki_root: Path) -> dict[str, object]:
    wiki_root = Path(wiki_root)
    issues: list[dict[str, str]] = []
    if not wiki_root.exists():
        issues.append(_issue("error", ".", "wiki_root_missing", "Wiki root does not exist.", str(wiki_root)))
        return {"ok": False, "error_count": 1, "warning_count": 0, "issues": issues}

    for path in sorted(wiki_root.rglob("*.md")):
        rel_path = _rel_path(path, wiki_root)
        parts = set(path.relative_to(wiki_root).parts)
        if ".git" in parts or "_archive" in parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            issues.append(_issue("warning", rel_path, "unreadable_markdown", "Markdown file could not be decoded as UTF-8.", str(exc)))
            continue
        frontmatter, body = _split_frontmatter(text)
        body_for_checks = "" if rel_path.startswith("raw/") else body

        if _is_generated_path(rel_path):
            missing = [key for key in GENERATED_REQUIRED_KEYS if key not in frontmatter]
            if missing:
                issues.append(_issue("error", rel_path, "generated_metadata_missing", "Generated report is missing required boundary metadata.", ", ".join(missing)))
            elif frontmatter.get("generated") is not True:
                issues.append(_issue("error", rel_path, "generated_flag_not_true", "Generated report path must declare generated: true.", f"generated: {frontmatter.get('generated')}"))
            for match in CANONICAL_PHRASES_RE.finditer(body_for_checks):
                if not _nearby_disclaimer(body_for_checks, match):
                    issues.append(_issue("error", rel_path, "generated_canonical_claim", "Generated page uses canonicalizing language without nearby evidence/status disclaimer.", match.group(0)))
            for match in ACTIONABLE_RE.finditer(body_for_checks):
                if not (_has_non_homepage_url(body_for_checks) and DATE_RE.search(body_for_checks)):
                    issues.append(_issue("error", rel_path, "actionable_without_evidence", "Actionable opportunity language lacks direct URL and date/deadline evidence.", match.group(0)))
            if "daily" in rel_path and "## Status" not in body_for_checks:
                issues.append(_issue("warning", rel_path, "generated_status_missing", "Reader-facing generated daily report is missing a status block.", rel_path))

        if _is_durable_path(rel_path):
            sources = frontmatter.get("sources")
            sources_empty = sources in (None, "", [])
            if sources_empty and STRONG_CLAIM_RE.search(body_for_checks):
                issues.append(_issue("warning", rel_path, "durable_sources_missing", "Durable page has strong claim markers but no sources frontmatter.", "sources: []"))

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {"ok": error_count == 0, "error_count": error_count, "warning_count": warning_count, "issues": issues}
