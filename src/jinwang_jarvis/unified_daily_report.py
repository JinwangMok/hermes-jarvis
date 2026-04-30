from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REQUIRED_SECTIONS = (
    "한눈에 보기",
    "오늘의 체크리스트",
    "주요 이슈",
    "개인 기회/공고 검토",
    "뉴스 카테고리별 브리핑",
    "근거 커버리지",
)
REQUIRED_CATEGORY_ORDER = (
    ("politics", "정치"),
    ("economy", "경제"),
    ("society", "사회"),
    ("culture", "문화"),
    ("world", "국제"),
    ("technology", "기술"),
    ("entertainment", "예능"),
)
REQUIRED_ISSUE_FIELDS = ("출처 성격", "확인된 사실", "왜 중요한가", "오늘 할 일", "근거", "불확실성")
URL_PATTERN = re.compile(r"https?://[^\s<>\]]+")
URL_TRAILING_PUNCTUATION = ".,;:)]}，。"


@dataclass(frozen=True)
class OpportunityCandidate:
    title: str
    official_url: str = ""
    deadline_window: str = ""
    eligibility: str = ""
    support_contents: str = ""
    evidence_note: str = ""


@dataclass(frozen=True)
class UnifiedDailyReport:
    report_date: str
    markdown: str
    markdown_path: Path | None = None
    pdf_path: Path | None = None


def _safe_text(value: object, fallback: str = "확인 필요") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or fallback


def _markdown_link(label: str, url: str) -> str:
    safe_label = re.sub(r"[\[\]\n\r]+", " ", _safe_text(label, "원문 링크")).strip()
    return f"[{safe_label or '원문 링크'}]({url})"


def _split_url_suffix(raw_url: str) -> tuple[str, str]:
    suffix = ""
    url = raw_url
    while url and url[-1] in URL_TRAILING_PUNCTUATION:
        suffix = url[-1] + suffix
        url = url[:-1]
    return url, suffix


def _label_visible_urls(text: str, label: str = "원문 링크") -> str:
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        if match.start() >= 2 and text[match.start() - 2 : match.start()] == "](":
            return match.group(0)
        url, suffix = _split_url_suffix(match.group(0))
        if not url:
            return match.group(0)
        counter += 1
        link_label = label if counter == 1 else f"{label} {counter}"
        return f"{_markdown_link(link_label, url)}{suffix}"

    return URL_PATTERN.sub(replace, text)


def _format_official_url(url: str) -> str:
    cleaned_url = str(url or "").strip()
    if not cleaned_url:
        return "상세 공식 URL 미확인"
    return _markdown_link("공식 공고 링크", cleaned_url)


def _first_url(text: str) -> str:
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(".,)") if match else "https://news.google.com/"


def _section_body(markdown: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", markdown, flags=re.M)
    if not match:
        return ""
    next_match = re.search(r"^##\s+", markdown[match.end() :], flags=re.M)
    end = match.end() + next_match.start() if next_match else len(markdown)
    return markdown[match.end() : end].strip()


def _extract_issue_cards(hot_issue_markdown: str, report_date: str) -> list[list[str]]:
    if not hot_issue_markdown.strip():
        return []
    matches = list(re.finditer(r"^###\s+(.+)$", hot_issue_markdown, flags=re.M))
    cards: list[list[str]] = []
    for index, match in enumerate(matches[:6]):
        title = re.sub(r"^\d{1,2}\s*[.)]\s+", "", match.group(1)).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(hot_issue_markdown)
        block = hot_issue_markdown[start:end].strip()
        url = _first_url(block)
        if all(field in block for field in REQUIRED_ISSUE_FIELDS):
            cards.extend([[f"### {title}"], [_label_visible_urls(line) for line in block.splitlines()], [""]])
            continue
        summary = _safe_text(re.sub(r"[*_`#>-]", " ", block), "기존 핫이슈 산출물에 제목 중심 항목만 있어 세부 사실은 원문 확인이 필요합니다.")[:220]
        cards.append(
            [
                f"### {title}",
                "- 출처 성격: 검증 전 후보.",
                f"- 확인된 사실: {summary}",
                "- 왜 중요한가: 오늘의 핫이슈 후보로 포착되어 원문 기준의 사실 확인이 필요합니다.",
                "- 오늘 할 일: 제목만으로 판단하지 말고 연결된 원문에서 날짜, 주체, 발표 내용을 확인합니다.",
                f"- 근거: {_markdown_link('원문 링크', url)}, {report_date} 확인.",
                "- 불확실성: 기존 산출물에 구조화 필드가 부족해 세부 해석은 보류합니다.",
                "",
            ]
        )
    return cards


def _fallback_issue_card(report_date: str) -> list[str]:
    return [
        "### 주요 외부 이슈 원문 확인 대기",
        "- 출처 성격: 검증 전 후보.",
        "- 확인된 사실: 입력된 핫이슈 카드가 없어 뉴스와 공식 원문 확인을 우선합니다.",
        "- 왜 중요한가: 빈 보고서로 보이지 않도록 확인 범위와 한계를 명확히 남깁니다.",
        "- 오늘 할 일: 뉴스 센터와 공식 공고 원문을 확인한 뒤 다음 보고서에 반영합니다.",
        f"- 근거: {_markdown_link('뉴스 검색 링크', 'https://news.google.com/')}, {report_date} 확인.",
        "- 불확실성: 이 항목은 새 행동 후보를 뜻하지 않습니다.",
        "",
    ]


def _opportunity_status(candidate: OpportunityCandidate) -> tuple[str, list[str]]:
    missing: list[str] = []
    if not candidate.official_url or re.fullmatch(r"https?://(?:www\.)?(?:iris\.go\.kr|bokjiro\.go\.kr)/?", candidate.official_url.strip()):
        missing.append("상세 공식 URL")
    if not candidate.deadline_window:
        missing.append("접수기간/마감")
    if not candidate.eligibility:
        missing.append("지원대상/자격")
    if not candidate.support_contents:
        missing.append("지원내용")
    return ("신청 가능" if not missing else "검토 필요", missing)


def _render_opportunities(candidates: Iterable[OpportunityCandidate]) -> list[str]:
    items = list(candidates)
    lines = ["## 개인 기회/공고 검토", "", "공식 상세 URL, 접수기간/마감, 지원대상/자격, 지원내용이 모두 확인된 항목만 행동 후보로 올립니다.", ""]
    if not items:
        lines.extend([
            "- **신청 가능한 공고 없음** — 입력된 개인 기회/공고 후보 artifact가 없거나 검증된 항목이 없습니다.",
            "- **처리 기준** — 후보가 있더라도 필수 근거가 빠지면 검토 필요 또는 보류로 남깁니다.",
            "",
        ])
        return lines
    for item in items:
        status, missing = _opportunity_status(item)
        lines.extend(
            [
                f"- **{_label_visible_urls(item.title)}** — 상태: **{status}**.",
                f"  - 공고 URL: {_format_official_url(item.official_url)}",
                f"  - 접수기간/마감: {_label_visible_urls(_safe_text(item.deadline_window))}",
                f"  - 지원대상/자격: {_label_visible_urls(_safe_text(item.eligibility))}",
                f"  - 지원내용: {_label_visible_urls(_safe_text(item.support_contents))}",
                f"  - 판단 근거: {_label_visible_urls(_safe_text(item.evidence_note), '근거 링크')}",
                f"  - 보류 사유: {', '.join(missing) if missing else '필수 근거 충족'}",
            ]
        )
    lines.append("")
    return lines


def _group_news_items(news_items: Iterable[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in news_items:
        category = str(item.get("category") or "").replace("it-science", "technology")
        grouped.setdefault(category, []).append(item)
    return grouped


def _render_category_briefing(news_items: Iterable[dict[str, object]], report_date: str) -> list[str]:
    grouped = _group_news_items(news_items)
    lines = ["## 뉴스 카테고리별 브리핑", "", "카테고리별 항목은 제목 나열 대신 출처 성격, 확인된 사실, 오늘 할 일, 근거, 불확실성을 고정 형식으로 남깁니다.", ""]
    for category_key, ko in REQUIRED_CATEGORY_ORDER:
        bucket = grouped.get(category_key, [])[:3]
        lines.extend([f"### {ko}"])
        if bucket:
            titles = "; ".join(_safe_text(item.get("title")) for item in bucket)
            first = bucket[0]
            url = str(first.get("url") or "https://news.google.com/")
            summary = _safe_text(first.get("body_text") or first.get("summary") or first.get("title"))[:220]
            provider = _safe_text(first.get("provider"), "news")
            source = _safe_text(first.get("source") or first.get("site"), provider)
            source_link = _markdown_link(source, url)
            lines.extend(
                [
                    "- 출처 성격: 보도.",
                    f"- 확인된 사실: {ko} 분야에서 {titles} 항목이 수집됐습니다. 대표 요약: {summary}",
                    f"- 왜 중요한가: {ko} 분야의 정책·시장·사회 흐름을 원문 기준으로 확인하기 위한 독자용 브리핑입니다.",
                    f"- 오늘 할 일: {source} 원문을 열어 발표 주체, 날짜, 수치, 후속 조치를 확인합니다.",
                    f"- 근거: {provider} / {source_link} / {first.get('published_at') or report_date} / hash {str(first.get('content_hash') or '')[:12] or 'n/a'}",
                    "- 불확실성: 수집 요약이므로 제목만으로 사실관계나 영향 범위를 단정하지 않습니다.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "- 출처 성격: 보도.",
                    f"- 확인된 사실: {ko} 분야에서 검증 가능한 기사 입력이 없습니다.",
                    f"- 왜 중요한가: {ko} 카테고리가 비어도 누락으로 숨기지 않고 확인 공백을 표시합니다.",
                    "- 오늘 할 일: 뉴스 원문 목록을 다시 수집하거나 수동으로 공식 보도자료를 확인합니다.",
                    f"- 근거: {_markdown_link('뉴스 검색 링크', 'https://news.google.com/')}, {report_date} 확인.",
                    "- 불확실성: 기사 입력 부재는 이슈 부재가 아니라 수집 공백일 수 있습니다.",
                    "",
                ]
            )
    return lines


def compose_unified_daily_report(
    *,
    report_date: str,
    hot_issue_markdown: str = "",
    news_items: Iterable[dict[str, object]] = (),
    opportunity_candidates: Iterable[OpportunityCandidate] = (),
) -> UnifiedDailyReport:
    news_items_list = list(news_items)
    opportunity_list = list(opportunity_candidates)
    issue_cards = _extract_issue_cards(hot_issue_markdown, report_date) or [_fallback_issue_card(report_date)]
    qualified_count = sum(1 for item in opportunity_list if _opportunity_status(item)[0] == "신청 가능")
    lines = [
        "---",
        f"title: 오늘의 핫이슈 리포트 — {report_date}",
        f"created: {report_date}",
        f"updated: {report_date}",
        "type: query",
        "subtype: generated-daily-report",
        "tags: [jarvis, intelligence, report, daily, hot-issues]",
        "owner: jarvis",
        "authority: derived",
        "generated: true",
        "generator: jinwang-jarvis-unified-daily-report",
        "refresh_policy: overwrite",
        "summary: Unified daily hot-issues report; opportunity radar merged into the report surface",
        "---",
        "",
        f"# 오늘의 핫이슈 리포트 — {report_date}",
        "",
        f"- 보고 기준 시각: {report_date} 09:00 KST",
        "- 해석 원칙: 생성 보고서는 조언형/파생 산출물이며 원문 확인 전 확정 사실로 승격하지 않습니다.",
        "- 구성 원칙: 섹션 배치, 표기, PDF 경로는 프로그램이 결정하고 생성 문장은 검증된 필드 안에만 배치합니다.",
        "",
        "## 한눈에 보기",
        "",
        f"오늘 보고서는 주요 이슈 {len(issue_cards)}개 카드, 뉴스 카테고리 {len(REQUIRED_CATEGORY_ORDER)}개, 개인 기회 후보 {len(opportunity_list)}개를 하나의 표면에서 검토합니다.",
        f"신청 가능으로 표시된 개인 기회는 {qualified_count}개이며, 필수 근거가 부족한 항목은 검토 필요 또는 보류로 남깁니다.",
        "",
        "## 오늘의 체크리스트",
        "",
        "- 주요 이슈는 공식 원문 또는 보도 원문에서 날짜와 발표 주체를 확인합니다.",
        "- 개인 기회/공고는 상세 공식 URL, 접수기간/마감, 지원대상/자격, 지원내용이 모두 있을 때만 신청 가능으로 봅니다.",
        "- 뉴스 카테고리는 정치·경제·사회·문화·국제·기술·예능을 모두 확인해 공백도 기록합니다.",
        "",
        "## 주요 이슈",
        "",
    ]
    for card in issue_cards:
        lines.extend(card)
    lines.extend(_render_opportunities(opportunity_list))
    lines.extend(_render_category_briefing(news_items_list, report_date))
    lines.extend(
        [
            "## 근거 커버리지",
            "",
            f"- 주요 이슈 카드: {len(issue_cards)}개",
            f"- 뉴스 입력 항목: {len(news_items_list)}개",
            f"- 개인 기회 후보: {len(opportunity_list)}개",
            f"- 필수 카테고리: {', '.join(ko for _, ko in REQUIRED_CATEGORY_ORDER)}",
            "- 계약: 생성 보고서는 wiki contract에 따라 조언형/파생 산출물이며 원문 근거 없이는 행동 가능 또는 확정 사실을 암시하지 않습니다.",
            "",
        ]
    )
    markdown = "\n".join(lines).rstrip() + "\n"
    errors = validate_unified_daily_report(markdown)
    if errors:
        raise ValueError("unified daily report validation failed: " + "; ".join(errors))
    return UnifiedDailyReport(report_date=report_date, markdown=markdown)


def validate_unified_daily_report(markdown: str) -> list[str]:
    errors: list[str] = []
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^##\s+{re.escape(section)}\s*$", markdown, flags=re.M):
            errors.append(f"missing required section: {section}")
    category_body = _section_body(markdown, "뉴스 카테고리별 브리핑")
    for _, ko in REQUIRED_CATEGORY_ORDER:
        if not re.search(rf"^###\s+{re.escape(ko)}\s*$", category_body, flags=re.M):
            errors.append(f"missing required news category: {ko}")
    if "## Appendix" in markdown or "####" in markdown:
        errors.append("category briefing must not render as raw appendix or shallow #### bullets")
    opportunity_body = _section_body(markdown, "개인 기회/공고 검토")
    if "# Personal Opportunity Radar" in opportunity_body:
        errors.append("personal opportunity radar must be merged, not rendered as standalone report")
    return errors


def _load_json_items(path: Path | None) -> list[dict[str, object]]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("opportunities") or payload.get("candidates") or []
        if isinstance(raw_items, list):
            return [item for item in raw_items if isinstance(item, dict)]
    return []


def load_opportunity_candidates(path: Path | None) -> list[OpportunityCandidate]:
    candidates: list[OpportunityCandidate] = []
    for item in _load_json_items(path):
        candidates.append(
            OpportunityCandidate(
                title=_safe_text(item.get("title") or item.get("name"), "제목 미확인 후보"),
                official_url=str(item.get("official_url") or item.get("url") or item.get("notice_url") or ""),
                deadline_window=str(item.get("deadline_window") or item.get("deadline") or item.get("window") or ""),
                eligibility=str(item.get("eligibility") or item.get("target") or item.get("지원대상") or ""),
                support_contents=str(item.get("support_contents") or item.get("support") or item.get("지원내용") or ""),
                evidence_note=str(item.get("evidence_note") or item.get("summary") or item.get("note") or ""),
            )
        )
    return candidates


def write_unified_daily_report(
    *,
    report_date: str,
    hot_issue_markdown: str = "",
    news_items: Iterable[dict[str, object]] = (),
    opportunity_candidates: Iterable[OpportunityCandidate] = (),
    wiki_root: Path,
    workspace_root: Path,
) -> dict[str, str | int]:
    news_items_list = list(news_items)
    opportunity_list = list(opportunity_candidates)
    report = compose_unified_daily_report(
        report_date=report_date,
        hot_issue_markdown=hot_issue_markdown,
        news_items=news_items_list,
        opportunity_candidates=opportunity_list,
    )
    markdown_path = wiki_root / "reports" / "hot-issues" / "daily" / f"{report_date}.md"
    pdf_path = workspace_root / "data" / "reports" / f"daily-hot-issues-{report_date}.pdf"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(report.markdown, encoding="utf-8")
    return {
        "markdown_path": str(markdown_path),
        "pdf_path": str(pdf_path),
        "report_date": report_date,
        "news_item_count": len(news_items_list),
        "opportunity_candidate_count": len(opportunity_list),
    }


def generate_unified_daily_report(
    *,
    report_date: str,
    wiki_root: Path,
    workspace_root: Path,
    hot_issue_path: Path | None = None,
    news_json_path: Path | None = None,
    opportunity_json_path: Path | None = None,
) -> dict[str, str | int]:
    hot_issue_markdown = hot_issue_path.read_text(encoding="utf-8") if hot_issue_path and hot_issue_path.exists() else ""
    news_items = _load_json_items(news_json_path or workspace_root / "data" / "news-center" / "latest.json")
    opportunities = load_opportunity_candidates(opportunity_json_path)
    return write_unified_daily_report(
        report_date=report_date,
        hot_issue_markdown=hot_issue_markdown,
        news_items=news_items,
        opportunity_candidates=opportunities,
        wiki_root=wiki_root,
        workspace_root=workspace_root,
    )
