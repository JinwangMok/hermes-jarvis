#!/usr/bin/env python3
"""Content-quality gate for reader-facing daily hot-issues reports.

This catches the failure mode where the PDF looks polished but reads like an
internal intelligence log: vague "signal" language, high-level claims without
facts, and issue cards that do not tell a first-time reader what happened.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BANNED_PATTERNS = [
    (re.compile(r"high-heat|low-heat", re.I), "use '중요도 높음/낮음' or explain the criterion"),
    (re.compile(r"weak signals?", re.I), "use '주목할 흐름' or '아직 확인 중인 변화'"),
    (re.compile(r"\b(advisory|canonical|deduped|fetch(?:ed)?|watch lane|action_required|registry|source audit)\b", re.I), "remove internal pipeline jargon from reader-facing PDF"),
    (re.compile(r"신호"), "do not use vague '신호'; say 발표/보도/공고/변화/검증 전 참고"),
    (re.compile(r"약신호|전략 잔존"), "replace analyst shorthand with reader-facing explanation"),
    (re.compile(r"Jinwang 관점|Hermes/Jarvis류"), "use reader-facing wording, not internal personalization labels"),
]

REQUIRED_ISSUE_FIELDS = ["확인된 사실", "왜 중요한가", "오늘 할 일", "근거", "불확실성"]
MIN_SOURCE_URLS = 1


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip()
    return text


def issue_blocks(text: str) -> list[tuple[str, str]]:
    text = strip_frontmatter(text)
    matches = list(re.finditer(r"^###\s+(.+)$", text, flags=re.M))
    blocks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((m.group(1).strip(), text[start:end].strip()))
    return blocks


def lint_text(text: str) -> list[str]:
    errors: list[str] = []
    body = strip_frontmatter(text)
    for pattern, message in BANNED_PATTERNS:
        for match in pattern.finditer(body):
            line_no = body[: match.start()].count("\n") + 1
            snippet = body[match.start() : match.end()]
            errors.append(f"line {line_no}: banned/unclear term '{snippet}' — {message}")

    blocks = issue_blocks(body)
    if not blocks:
        errors.append("no ### issue cards found")
        return errors

    for title, block in blocks:
        # Skip appendix-like sections accidentally using ### only if explicitly marked.
        if title.lower().startswith(("appendix", "source")):
            continue
        missing = [field for field in REQUIRED_ISSUE_FIELDS if field not in block]
        if missing:
            errors.append(f"issue '{title}' missing fields: {', '.join(missing)}")
        url_count = len(re.findall(r"https?://", block))
        if url_count < MIN_SOURCE_URLS and "신청 가능한 공고 없음" not in block:
            errors.append(f"issue '{title}' has no external source URL in the card")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown", type=Path)
    args = parser.parse_args()
    text = args.markdown.read_text(encoding="utf-8")
    errors = lint_text(text)
    if errors:
        print("daily hot-issues content lint failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1
    print("daily hot-issues content lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
