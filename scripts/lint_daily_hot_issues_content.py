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
    (re.compile(r"Jinwang 관점|Hermes/Jarvis류|Hermes/Jarvis식"), "use reader-facing wording, not internal personalization labels"),
    (re.compile(r"낮춘 기준"), "do not say the quality/selection criterion was lowered; say '확장 기준' or explain inclusion scope"),
]

REQUIRED_ISSUE_FIELDS = ["출처 성격", "확인된 사실", "왜 중요한가", "오늘 할 일", "근거", "불확실성"]
MIN_SOURCE_URLS = 1
SOURCE_TYPE_PATTERN = re.compile(r"(?:^|\n)\s*-?\s*출처 성격\s*:\s*(공식 발표|공식 블로그|공식 공고|보도|커뮤니티 소개|개인 게시물 주장|분석/칼럼|GitHub 공개 프로젝트|내부 운영 변경|검증 전 후보)\s*[.。]?\s*(?:\n|$)")
INTERNAL_OPS_PATTERN = re.compile(r"\b(Jarvis|Hermes)\b|운영 보강|GitHub 변경|커밋|푸시|자동 확인|모니터링 경로|내부 설정")
OPPORTUNITY_PATTERN = re.compile(r"(공고|지원사업|신청|접수|마감|자격|eligibility|deadline|IRIS|복지로|청년|R&D|정부 ?사업)", re.I)
OPPORTUNITY_REQUIRED_TERMS = [
    (re.compile(r"(공식 공고|공고 URL|notice URL|상세 URL|첨부파일|RFP)", re.I), "official notice URL/detail"),
    (re.compile(r"(마감|접수기간|deadline|window|기간)", re.I), "deadline/window"),
    (re.compile(r"(자격|eligibility|지원대상|신청대상|기관 조건|개인 조건)", re.I), "eligibility"),
    (re.compile(r"(지원내용|지원 규모|예산|금액|support contents|사업비)", re.I), "support contents"),
]


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip()
    return text


def issue_blocks(text: str) -> list[tuple[str, str, str]]:
    text = strip_frontmatter(text)
    matches = list(re.finditer(r"^###\s+(.+)$", text, flags=re.M))
    section_matches = list(re.finditer(r"^##\s+(.+)$", text, flags=re.M))
    blocks: list[tuple[str, str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        next_h3 = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        next_h2 = next((sm.start() for sm in section_matches if sm.start() > m.start()), len(text))
        end = min(next_h3, next_h2)
        section = ""
        for sm in section_matches:
            if sm.start() < m.start():
                section = sm.group(1).strip()
            else:
                break
        blocks.append((m.group(1).strip(), text[start:end].strip(), section))
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

    for title, block, section in blocks:
        # Skip appendix-like sections accidentally using ### only if explicitly marked.
        if title.lower().startswith(("appendix", "source")):
            continue
        missing = [field for field in REQUIRED_ISSUE_FIELDS if field not in block]
        if missing:
            errors.append(f"issue '{title}' missing fields: {', '.join(missing)}")
        if "출처 성격" in block and not SOURCE_TYPE_PATTERN.search(block):
            errors.append(
                f"issue '{title}' has unclear 출처 성격 — use one of 공식 발표/공식 블로그/공식 공고/보도/커뮤니티 소개/개인 게시물 주장/분석/칼럼/GitHub 공개 프로젝트/검증 전 후보"
            )
        if INTERNAL_OPS_PATTERN.search(title) or INTERNAL_OPS_PATTERN.search(block):
            in_internal_section = section in {"내부 운영", "운영 메모"}
            explicitly_internal = bool(re.search(r"(?:^|\n)\s*-?\s*출처 성격\s*:\s*내부 운영 변경\s*[.。]?\s*(?:\n|$)", block))
            if not (in_internal_section and explicitly_internal):
                errors.append(f"issue '{title}' appears to mix internal ops into main hot issues; move to an internal ops appendix")
            if title.startswith("Jarvis") or title.startswith("Hermes"):
                errors.append(f"issue '{title}' is an internal ops item, not a reader-facing external hot issue")
        url_count = len(re.findall(r"https?://", block))
        if url_count < MIN_SOURCE_URLS and "신청 가능한 공고 없음" not in block:
            errors.append(f"issue '{title}' has no external source URL in the card")
        if OPPORTUNITY_PATTERN.search(title) or OPPORTUNITY_PATTERN.search(block):
            # Generic homepages are not enough when a report may imply a policy/R&D/life opportunity.
            if re.search(r"https?://(?:www\.)?(?:iris\.go\.kr|bokjiro\.go\.kr)/?\s*[,.)]?", block):
                errors.append(f"issue '{title}' opportunity evidence is only a generic homepage; include a direct notice/detail URL or mark as not verified")
            for pattern, label in OPPORTUNITY_REQUIRED_TERMS:
                if not pattern.search(block):
                    errors.append(f"issue '{title}' opportunity contract missing {label}")
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
