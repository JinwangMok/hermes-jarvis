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
    (re.compile(r"Jinwang 관점|Hermes/ZeusOS류|Hermes/ZeusOS식|Hermes/ZeusOS류|Hermes/ZeusOS식"), "use reader-facing wording, not internal personalization labels"),
    (re.compile(r"낮춘 기준"), "do not say the quality/selection criterion was lowered; say '확장 기준' or explain inclusion scope"),
    (re.compile(r"검증 전 후보"), "do not promote unverified watch candidates into reader-facing main issues"),
    (re.compile(r"(?:분류\s*:|열기\s*:|중요도\s*\d|모멘텀\s*\d|momentum\s*[0-9.]+|importance\s*[0-9.]+)", re.I), "remove internal scoring/debug metadata from reader-facing PDF"),
]

REQUIRED_ISSUE_FIELDS = ["출처 성격", "확인된 사실", "왜 중요한가", "오늘 할 일", "근거", "불확실성"]
ISSUE_CARD_SECTIONS = {"주요 이슈", "뉴스 카테고리별 브리핑", "내부 운영", "운영 메모"}
MIN_SOURCE_URLS = 1
SOURCE_TYPE_PATTERN = re.compile(r"(?:^|\n)\s*-?\s*출처 성격\s*:\s*(공식 발표|공식 블로그|공식 공고|보도|커뮤니티 소개|개인 게시물 주장|분석/칼럼|GitHub 공개 프로젝트|내부 운영 변경|검증 전 후보)\s*[.。]?\s*(?:\n|$)")
INTERNAL_OPS_PATTERN = re.compile(r"\bZeusOS\b|운영 보강|GitHub 변경|커밋|푸시|자동 확인|모니터링 경로|내부 설정")
OPPORTUNITY_PATTERN = re.compile(r"(공고|지원사업|신청|접수|마감|자격|eligibility|deadline|IRIS|복지로|청년|정부 ?사업)", re.I)
OPPORTUNITY_REQUIRED_TERMS = [
    (re.compile(r"(공식 공고|공고 URL|notice URL|상세 URL|첨부파일|RFP)", re.I), "official notice URL/detail"),
    (re.compile(r"(마감|접수기간|deadline|window|기간)", re.I), "deadline/window"),
    (re.compile(r"(자격|eligibility|지원대상|신청대상|기관 조건|개인 조건)", re.I), "eligibility"),
    (re.compile(r"(지원내용|지원 규모|예산|금액|support contents|사업비)", re.I), "support contents"),
]
GENERIC_WHY_PATTERNS = [
    re.compile(r"분야의 정책·시장·사회 흐름을 원문 기준으로 확인하기 위한 독자용 브리핑"),
    re.compile(r"오늘의 핫이슈 후보로 포착되어 원문 기준의 사실 확인이 필요"),
    re.compile(r"주요 흐름을 파악하기 위한 참고 기사"),
    re.compile(r"(?:정치|경제|사회|문화|국제|기술|예능) 분야에서는.*(?:대표 요약|구체 변화|후속 공지 여부|원문 기준)")
]
CATEGORY_META_FILLER_PATTERN = re.compile(
    r"(?:정치|경제|사회|문화|국제|기술|예능) 분야(?:에서|에서는).*"
    r"(?:대표 요약|구체 변화|항목이 수집|정책·시장·사회 파급|원문 기준)",
)
SOURCE_GROUNDED_PREFIX_PATTERN = re.compile(r"^(?:본 기사|본 공지|본 논문|이 기사|이 공지|이 논문)(?:는|은|에서)\s+")
THIN_CONFIRMED_FACT_PATTERN = re.compile(
    r"^(?:[^.。\n]{0,80})?(?:항목이\s*)?수집됐습니다[.。]?$|"
    r"^(?:[^.。\n]{0,80})?후보로\s*포착(?:되어|됨)[^.。\n]*[.。]?$|"
    r"^(?:watch\s*)?후보에\s*항목이\s*들어왔다[.。]?$",
    re.I,
)
GENERIC_ACTION_PATTERN = re.compile(r"제목만으로 판단하지 말고|원문을 확인합니다[.。]?$|발표 주체, 날짜, 수치, 후속 조치를 확인")
PROVIDER_BOILERPLATE_PATTERN = re.compile(
    r"이동\s*통신망을\s*이용하여\s*음성을\s*재생하면|"
    r"기사의\s*섹션\s*정보는\s*해당\s*언론사의\s*분류|"
    r"기사\s*섹션\s*정보가\s*정치/선거를\s*포함하는\s*경우|"
    r"섹션별로\s*기사의\s*댓글\s*제공\s*여부와\s*정렬방식을\s*언론사(?:가|\s*확인:)?\s*직접\s*결정|"
    r"언론사의\s*결정에\s*따라\s*동일한\s*섹션이라도\s*기사\s*단위로\s*댓글\s*제공여부|"
    r"댓글\s*운영\s*방식\s*및\s*운영규정에\s*따른\s*삭제나\s*이용제한\s*조치|"
    r"네이버가\s*직접\s*수행|"
    r"단,?\s*일부(?:\s|$)|"
    r"본문의\s*검색\s*링크[^\n.。!?！？]*AI\s*자동\s*인식|"
    r"일부에\s*대해서[^\n.。!?！？]*(?:미제공|전체\s*검색\s*결과)|"
    r"언론사는\s*개별\s*기사를\s*2개\s*이상\s*섹션으로\s*중복\s*분류|"
    r"서비스\s*정책에\s*따라[^\n.。!?！？]*(?:댓글|정렬방식|정치/선거섹션)|"
    r"이\s*기사를\s*본\s*이용자들이\s*함께\s*많이\s*본\s*기사|"
    r"해당\s*기사와\s*유사한\s*기사|"
    r"관심\s*기사\s*등을\s*자동\s*추천|"
    r"Copyright\s*ⓒ?|무단\s*전재|All\s*rights\s*reserved",
    re.I,
)


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


def _field_value(block: str, field: str) -> str:
    labels = "|".join(map(re.escape, REQUIRED_ISSUE_FIELDS))
    pattern = re.compile(rf"(?:^|\n)\s*-\s*{re.escape(field)}\s*:\s*(.*?)(?=\n\s*-\s*(?:{labels})\s*:|\Z)", re.S)
    match = pattern.search(block)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _wordish_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9가-힣]+", text))


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

    main_issue_blocks = [(title, block, section) for title, block, section in blocks if section == "주요 이슈"]
    if not main_issue_blocks and "승격된 주요 이슈 없음" not in body:
        errors.append("주요 이슈 section has no reader-facing issue cards")

    for title, block, section in blocks:
        # Ignore subsection headings used for reader navigation/dashboard outside card sections.
        if section not in ISSUE_CARD_SECTIONS:
            continue
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
            if title.startswith("ZeusOS") or title.startswith("Hermes"):
                errors.append(f"issue '{title}' is an internal ops item, not a reader-facing external hot issue")
        url_count = len(re.findall(r"https?://", block))
        if url_count < MIN_SOURCE_URLS and "신청 가능한 공고 없음" not in block:
            errors.append(f"issue '{title}' has no external source URL in the card")
        confirmed_fact = _field_value(block, "확인된 사실")
        why_it_matters = _field_value(block, "왜 중요한가")
        action = _field_value(block, "오늘 할 일")
        if confirmed_fact and PROVIDER_BOILERPLATE_PATTERN.search(confirmed_fact):
            errors.append(f"issue '{title}' contains provider boilerplate in confirmed fact — extract real article body or hold the category")
        if why_it_matters and PROVIDER_BOILERPLATE_PATTERN.search(why_it_matters):
            errors.append(f"issue '{title}' contains provider boilerplate in why-it-matters — do not derive impact from portal chrome")
        if action and PROVIDER_BOILERPLATE_PATTERN.search(action):
            errors.append(f"issue '{title}' contains provider boilerplate in action — inspect the article body instead")
        if section == "주요 이슈":
            if confirmed_fact and THIN_CONFIRMED_FACT_PATTERN.search(confirmed_fact):
                errors.append(f"issue '{title}' has thin confirmed fact — explain what actually happened, not only that an item was collected")
            if confirmed_fact and CATEGORY_META_FILLER_PATTERN.search(confirmed_fact):
                errors.append(f"issue '{title}' has category/meta filler instead of a source-content summary")
            if confirmed_fact and not SOURCE_GROUNDED_PREFIX_PATTERN.search(confirmed_fact) and CATEGORY_META_FILLER_PATTERN.search(block):
                errors.append(f"issue '{title}' lacks source-content summary — confirmed fact must summarize what the source actually says")
            if why_it_matters and any(pattern.search(why_it_matters) for pattern in GENERIC_WHY_PATTERNS):
                errors.append(f"issue '{title}' has generic why-it-matters — state concrete impact on research, product, infrastructure, market, policy, or Jinwang's work")
            if why_it_matters and _wordish_count(why_it_matters) < 12:
                errors.append(f"issue '{title}' has too little reader value in why-it-matters")
            if action and GENERIC_ACTION_PATTERN.search(action) and _wordish_count(action) < 14:
                errors.append(f"issue '{title}' has keyword-only action — specify what to inspect, compare, record, or defer")
        if section == "주요 이슈" and (OPPORTUNITY_PATTERN.search(title) or OPPORTUNITY_PATTERN.search(block)):
            # Generic homepages are not enough when a main issue card may imply a policy/R&D/life opportunity.
            # Category news briefs can naturally contain words like "접수" or "신청" without being user-actionable
            # opportunity recommendations, so do not apply the opportunity evidence contract there.
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
