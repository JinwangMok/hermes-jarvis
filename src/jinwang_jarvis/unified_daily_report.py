from __future__ import annotations

import json
import html
import importlib.util
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .news_crawlers.adapters import extract_article_body

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
URL_PATTERN = re.compile(r"https?://[^\s<>\]\)\"']+")
URL_TRAILING_PUNCTUATION = ".,;:)]}，。"


class DeliveryGateError(RuntimeError):
    """Raised when the representative Daily Hot Issues delivery gate fails."""

    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        stage = result.get("failed_stage") or "unknown"
        errors = result.get("errors") or []
        detail = "; ".join(str(error) for error in errors) if isinstance(errors, list) else str(errors)
        super().__init__(f"daily hot-issues delivery gate failed at {stage}: {detail}")


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


@dataclass(frozen=True)
class ArticleBrief:
    actor: str
    fact: str
    why_seed: str
    action_focus: str


def _safe_text(value: object, fallback: str = "확인 필요") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or fallback


def _reader_text(value: object, fallback: str = "확인 필요") -> str:
    """Return reader-facing prose with raw HTML/URLs stripped from source snippets."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[[^\]]+\]\((https?://[^\)]+)\)", lambda m: m.group(0).split("]", 1)[0].lstrip("["), text)
    text = URL_PATTERN.sub(" ", text)
    text = text.replace("신호", "지표")
    text = re.sub(r"\s+", " ", text).strip()
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
    match = URL_PATTERN.search(text)
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
    for index, match in enumerate(matches[:8]):
        title = _reader_text(re.sub(r"^\d{1,2}\s*[.)]\s+", "", match.group(1)).strip())
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(hot_issue_markdown)
        block = hot_issue_markdown[start:end].strip()
        url = _first_url(block)
        if all(field in block for field in REQUIRED_ISSUE_FIELDS):
            cards.extend([[f"### {title}"], [_label_visible_urls(line) for line in block.splitlines()], [""]])
            continue
        candidate = _compose_domain_hot_issue_card(title, block, url, report_date)
        if candidate:
            cards.append(candidate)
        if len(cards) >= 4:
            break
    return cards


def _extract_labeled_value(block: str, label: str) -> str:
    match = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+?)(?=\n\*\*[^\n]+:\*\*|\Z)", block, flags=re.S)
    return _reader_text(match.group(1), "") if match else ""


def _is_domain_hot_issue(text: str) -> bool:
    return bool(re.search(r"Ouroboros|Agent\s*OS|Claude|Codex|Hermes|OpenCode|agentic|에이전트|AI\s*infra|Cloud|Kubernetes|CNCF", text, flags=re.I))


def _compose_domain_hot_issue_card(title: str, block: str, url: str, report_date: str) -> list[str] | None:
    raw_summary = _extract_labeled_value(block, "내용 요약") or _reader_text(block, "")
    preamble = _reader_text(block.split("**분류:**", 1)[0].split("**내용 요약:**", 1)[0], "")
    if _wordish_count(preamble) > _wordish_count(raw_summary):
        raw_summary = f"{raw_summary}. {preamble}"
    source = _extract_labeled_value(block, "출처") or url
    combined = f"{title} {raw_summary} {source}"
    if not _is_domain_hot_issue(combined):
        return None
    if re.search(r"^(?:docs[:(]|feat:|fix\b|chore\b|merge pull request|promote)|dev build|Co-Authored-By|GitHub Actions CI", title, flags=re.I):
        return None
    summary = _reader_text(raw_summary or title, "")
    summary = re.sub(r"<img\b.*", " ", summary, flags=re.I | re.S)
    summary = re.sub(r"\b(?:nitter\.net|github\.com|x\.com)/\S+", " ", summary, flags=re.I)
    summary = re.sub(r"\s+", " ", summary).strip()
    if _wordish_count(summary) < 6:
        summary = _reader_text(f"{title}. {raw_summary}", "")
    fact = _first_sentence(summary, 260)
    if re.search(r"\b(?:I/O journal|AgentProcess|benchmark|dataset|API|Kubernetes|vLLM|KServe)\b", summary, flags=re.I) and not re.search(
        r"\b(?:I/O journal|AgentProcess|benchmark|dataset|API|Kubernetes|vLLM|KServe)\b", fact, flags=re.I
    ):
        fact = summary[:260].rstrip(" ,.;")
    if _wordish_count(fact) < 8 or re.search(r"^wow\b|^Our podcast is live!?$", fact, flags=re.I):
        fact = summary[:260].rstrip(" ,.;")
    if _wordish_count(fact) < 6:
        return None
    why = "Agent OS·에이전트 실행 방식·Claude/Codex/Hermes류 도구 사용 패턴과 직접 연결되는 변화라서, 진왕님이 따라가야 할 AI/Agent 시스템 설계 변화입니다."
    if re.search(r"spec|specifying|verification|verifiable|constraint", combined, flags=re.I):
        why = "프롬프트보다 검증 가능한 명세와 제약을 앞세우는 흐름이라서, 에이전트 벤치마크·운영 harness 설계 기준에 바로 영향을 줍니다."
    action = "원문에서 실제 데모 내용, 공개된 repo/릴리스 목표, 기존 Claude Code·Codex·Hermes 사용 방식과 달라진 점만 확인합니다."
    source_label = "원문 링크"
    source_url = _first_url(source if source.startswith("http") else block)
    return [
        f"### {title[:140].rstrip()}",
        "- 출처 성격: 커뮤니티 소개.",
        f"- 확인된 사실: {fact}",
        f"- 왜 중요한가: {why}",
        f"- 오늘 할 일: {action}",
        f"- 근거: {_markdown_link(source_label, source_url)}, {report_date} 확인.",
        "- 불확실성: 커뮤니티 게시물 기반이므로 실제 공개 범위와 릴리스 상태는 원문·저장소에서 재확인해야 합니다.",
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
        return lines + ["- 오늘 검증된 개인 기회/공고 후보는 없습니다.", "- 보류 기준: 공식 상세 URL, 접수기간/마감, 지원대상/자격, 지원내용 중 하나라도 비어 있으면 행동 후보로 올리지 않습니다.", ""]
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


PROVIDER_BOILERPLATE_PATTERNS = (
    r"이동\s*통신망을\s*이용하여\s*음성을\s*재생하면\s*별도의\s*데이터\s*통화료가\s*부과될\s*수\s*있습니다[.。!?！？]?",
    r"Copyright\s*ⓒ?\s*[^.。!?！？]{0,100}(?:All\s*rights\s*reserved|무단\s*전재|무단전재)?[^.。!?！？]*[.。!?！？]?",
    r"All\s*rights\s*reserved[.。!?！？]?",
    r"무단\s*전재[^.。!?！？]*(?:금지|禁)[^.。!?！？]*[.。!?！？]?",
    r"기사의\s*섹션\s*정보는\s*해당\s*언론사의\s*분류를\s*따르고\s*있습니다[.。!?！？]?",
    r"기사\s*섹션\s*정보가\s*정치/선거를\s*포함하는\s*경우[^.。!?！？]*[.。!?！？]?",
    r"섹션별로\s*기사의\s*댓글\s*제공\s*여부와\s*정렬방식을\s*언론사(?:가|\s*확인:)?\s*직접\s*결정합니다[.。!?！？]?",
    r"언론사의\s*결정에\s*따라\s*동일한\s*섹션이라도\s*기사\s*단위로\s*댓글\s*제공여부[^.。!?！？]*[.。!?！？]?",
    r"댓글\s*운영\s*방식\s*및\s*운영규정에\s*따른\s*삭제나\s*이용제한\s*조치[^.。!?！？]*[.。!?！？]?",
    r"네이버가\s*직접\s*수행합니다[.。!?！？]?",
    r"단,?\s*일부(?:\s|$)",
    r"본문의\s*검색\s*링크[^.。!?！？]*AI\s*자동\s*인식[^.。!?！？]*[.。!?！？]?",
    r"일부에\s*대해서[^.。!?！？]*(?:미제공|전체\s*검색\s*결과)[^.。!?！？]*[.。!?！？]?",
    r"언론사는\s*개별\s*기사를\s*2개\s*이상\s*섹션으로\s*중복\s*분류할\s*수\s*있습니다[.。!?！？]?",
    r"서비스\s*정책에\s*따라[^.。!?！？]*(?:댓글을\s*제공하지\s*않습니다|정렬방식을\s*언론사가\s*직접\s*결정합니다|정치/선거섹션\s*정책이\s*적용됩니다)[.。!?！？]?",
    r"이\s*기사를\s*본\s*이용자들이\s*함께\s*많이\s*본\s*기사[^.。!?！？]*[.。!?！？]?",
    r"해당\s*기사와\s*유사한\s*기사[^.。!?！？]*[.。!?！？]?",
    r"관심\s*기사\s*등을\s*자동\s*추천합니다[.。!?！？]?",
    r"함께\s*많이\s*본\s*뉴스[^.。!?！？]*[.。!?！？]?",
)


def _strip_provider_boilerplate(text: str) -> str:
    cleaned = _reader_text(text, "")
    for pattern in PROVIDER_BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip()


def _without_title_and_source_chrome(text: str, item: dict[str, object], title: str) -> str:
    residual = _normalize_reader_tokens(text)
    for token in (
        title,
        _reader_text(item.get("title"), ""),
        _reader_text(item.get("source"), ""),
        _reader_text(item.get("site"), ""),
        _reader_text(item.get("provider"), ""),
    ):
        normalized_token = _normalize_reader_tokens(token)
        if normalized_token:
            residual = residual.replace(normalized_token, " ")
    return re.sub(r"\s+", " ", residual).strip()


def _normalize_reader_tokens(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", " ", _reader_text(text, "").casefold()).strip()


def _news_source_content(item: dict[str, object]) -> str:
    """Return actual source-provided article/notice content; never fall back to title/provider chrome."""
    title_raw = _reader_text(item.get("title"), "")
    title = title_raw.casefold()
    for field in ("body_text", "body", "content", "description", "summary", "excerpt"):
        value = _reader_text(item.get(field), "")
        if not value or value.casefold() == title:
            continue
        cleaned = _strip_provider_boilerplate(value)
        cleaned_folded = cleaned.casefold()
        if not cleaned or cleaned_folded == title:
            continue
        if _wordish_count(_without_title_and_source_chrome(cleaned, item, title)) < 4:
            continue
        if title and cleaned_folded.replace(title, "").strip(" -—:·,.'\"“”‘’()[]") == "":
            continue
        if _wordish_count(cleaned) >= 10:
            return cleaned
    return ""


def _default_news_body_fetcher(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "jinwang-jarvis-unified-daily-report/0.1"})
    with urllib.request.urlopen(req, timeout=12) as response:  # noqa: S310 - public article URLs from Jarvis news artifacts
        raw = response.read(2_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _enrich_news_items_for_briefing(
    news_items: Iterable[dict[str, object]],
    *,
    body_fetcher: Callable[[str], str] | None,
    max_enrichments: int = 120,
) -> list[dict[str, object]]:
    fetcher = body_fetcher or _default_news_body_fetcher
    enriched: list[dict[str, object]] = []
    attempted = 0
    for raw in news_items:
        item = dict(raw)
        if _news_source_content(item) or attempted >= max_enrichments:
            enriched.append(item)
            continue
        url = str(item.get("url") or item.get("canonical_url") or "").strip()
        if not url.startswith(("http://", "https://")):
            enriched.append(item)
            continue
        attempted += 1
        try:
            extracted = extract_article_body(fetcher(url), url=url)
        except Exception as exc:
            item.setdefault("parse_status", "body_fetch_failed")
            item.setdefault("body_fetch_error", type(exc).__name__)
            enriched.append(item)
            continue
        if extracted and extracted.body_text:
            item["body_text"] = extracted.body_text
            item["canonical_url"] = extracted.canonical_url or item.get("canonical_url") or url
            item["parse_status"] = "body_extracted_for_report"
        else:
            item.setdefault("parse_status", "body_extract_empty")
        enriched.append(item)
    return enriched


def _wordish_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9가-힣]+", text))


def _first_sentence(text: str, max_chars: int = 220) -> str:
    cleaned = _reader_text(text, "")
    match = re.search(r"^(.+?[.。!?！？])(?:\s|$)", cleaned)
    sentence = match.group(1) if match else cleaned
    if len(sentence) > max_chars:
        sentence = sentence[:max_chars].rstrip() + "…"
    return sentence.rstrip(".。")


def _split_sentences(text: str) -> list[str]:
    cleaned = _reader_text(text, "")
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.。!?！？])\s+", cleaned)
    return [part.strip().rstrip(".。") for part in parts if _wordish_count(part) >= 4]


def _sentence_score(sentence: str) -> int:
    score = 0
    score += 4 * len(re.findall(r"\d+(?:\.\d+)?\s*(?:%|개|명|조|억|년|월|일|버전|배|건)?", sentence))
    score += 3 * len(re.findall(r"[A-Z][A-Za-z0-9.-]*(?:\s+[A-Z][A-Za-z0-9.-]*)*", sentence))
    score += 5 * len(re.findall(r"발표|공개|도입|변경|제거|인상|인하|낮추|높이|확대|축소|시행|출시|릴리스|업그레이드|마감|승인|합의", sentence))
    score += 3 * len(re.findall(r"전망|정책|기준|대상|관리자|운영자|보안|API|성장률|수출|내수|정식", sentence))
    if re.search(r"서론|일반 설명|배경|빠르게 바뀐다는", sentence):
        score -= 12
    return score


def _extract_actor(sentence: str, source: str) -> str:
    patterns = [
        r"^(.{2,60}?)(?:은|는|이|가)\s+(?:\d{4}년\s+\d{1,2}월\s+\d{1,2}일\s+)?(?:[^.。!?！？]{0,80}?)(?:발표|공개|밝혔|설명|안내|제시|전망|릴리스)",
        r"^(.{2,60}?)(?:은|는|이|가)\s+",
    ]
    for pattern in patterns:
        match = re.search(pattern, sentence)
        if match:
            actor = re.sub(r"^(기사|보도|관계자|서론 문장)\s*", "", match.group(1)).strip(" ,")
            if actor and not re.search(r"일반 설명|서론", actor):
                return actor
    return source


def _remove_actor_prefix(sentence: str, actor: str) -> str:
    if actor:
        sentence = re.sub(rf"^{re.escape(actor)}(?:은|는|이|가)\s+", "", sentence).strip()
    return sentence


def _join_brief_parts(parts: list[str], max_chars: int = 300) -> str:
    text = " ".join(part.strip().rstrip(".。") for part in parts if part.strip())
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return text


def _extract_article_brief(source_content: str, source: str) -> ArticleBrief:
    sentences = _split_sentences(source_content)
    if not sentences:
        summary = _first_sentence(source_content)
        return ArticleBrief(actor=source, fact=_source_content_fact(summary), why_seed=summary, action_focus=summary)

    ranked = sorted(enumerate(sentences), key=lambda pair: (_sentence_score(pair[1]), -pair[0]), reverse=True)
    main_index, main_sentence = ranked[0]
    actor = _extract_actor(main_sentence, source)
    main_fact = _remove_actor_prefix(main_sentence, actor)

    detail_candidates: list[tuple[int, str]] = []
    for index, sentence in enumerate(sentences):
        if index == main_index:
            continue
        if _sentence_score(sentence) >= 4 or re.search(r"전까지|예정|확인|점검|완료|근거|대상|수치|버전|후속", sentence):
            detail_candidates.append((index, _remove_actor_prefix(sentence, actor)))
    detail_candidates.sort(key=lambda pair: pair[0])
    details = [sentence for _, sentence in detail_candidates[:2]]

    label = "발표" if re.search(r"발표|공개|밝혔|설명|안내|제시|전망|릴리스", main_sentence) else "확인"
    fact_parts = [f"{actor} {label}: {main_fact}"]
    if details:
        fact_parts.append(f"후속 확인: {_join_brief_parts(details, 180)}")
    fact = _join_brief_parts(fact_parts)
    why_seed = _join_brief_parts([main_fact, *details], 220)
    action_focus = _join_brief_parts([main_sentence, *details], 260)
    return ArticleBrief(actor=actor, fact=fact, why_seed=why_seed, action_focus=action_focus)


def _brief_subject(summary: str) -> str:
    subject = re.sub(r"^(?:본 기사(?:는|에서)|본 공지(?:는|에서)|본 논문(?:은|에서))\s*", "", summary).strip()
    subject = re.sub(r"(?:다고 설명했다|라고 밝혔다|다고 밝혔다|했다|됐다|되었다)$", "", subject.rstrip(".。 ")).strip()
    return subject[:80].rstrip(" ,.")



def _source_content_fact(summary: str) -> str:
    summary = summary.strip().rstrip(".。")
    if re.search(r"[가-힣]$", summary):
        if summary.endswith("다"):
            return f"본 기사는 {summary}는 내용을 다뤘습니다."
        return f"본 기사는 {summary}라는 내용을 다뤘습니다."
    return f"본 기사는 ‘{summary}’라는 내용을 다뤘습니다."

def _grounded_why(summary: str) -> str:
    subject = _brief_subject(summary)
    if "성장률" in summary or "경제" in summary:
        return f"성장률 전망 하향은 {subject}라는 판단 변화를 뜻하므로 예산·R&D·기업 투자 판단의 전제치를 낮춰 잡아야 합니다."
    if "Kubernetes" in summary or "CNCF" in summary or "클러스터" in summary:
        return f"{subject}라는 변화는 클러스터 운영·보안·플랫폼 설계에서 바로 검토할 기술 부채와 채택 리스크를 만듭니다."
    if "논문" in summary or "모델" in summary or "AI" in summary:
        return f"{subject}라는 내용은 연구 아이디어, 벤치마크 기준, 에이전트/모델 활용 전략의 전제를 바꿀 수 있습니다."
    return f"{subject}라는 실제 변화가 확인되어 관련 의사결정의 전제와 후속 확인 범위를 구체적으로 좁힐 수 있습니다."


def _grounded_action(source: str, summary: str) -> str:
    if "성장률" in summary or "경제" in summary:
        return f"{source} 원문에서 성장률 조정 폭, 전망 변경 근거, 다음 발표·수정 시점을 확인합니다."
    if "Kubernetes" in summary or "CNCF" in summary:
        return f"{source} 원문에서 제안한 아키텍처, 적용 버전, 보안/운영 전제, 관련 프로젝트 링크를 확인합니다."
    if "논문" in summary or "모델" in summary or "AI" in summary:
        return f"{source} 원문에서 방법론, 데이터셋, 벤치마크 수치, 코드/모델 공개 여부를 확인합니다."
    return f"{source} 원문에서 발표 주체, 핵심 수치·조건, 적용 시점, 후속 조치가 무엇인지 확인합니다."


def _group_news_items(news_items: Iterable[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in news_items:
        category = str(item.get("category") or "").replace("it-science", "technology")
        grouped.setdefault(category, []).append(item)
    return grouped


def _issue_card_count(issue_cards: list[list[str]]) -> int:
    return sum(1 for block in issue_cards if block and block[0].startswith("### "))


def _readable_news_category_keys(news_items: Iterable[dict[str, object]]) -> set[str]:
    grouped = _group_news_items(news_items)
    return {
        category_key
        for category_key, _ in REQUIRED_CATEGORY_ORDER
        if any(_news_source_content(item) for item in grouped.get(category_key, []))
    }


def _render_reader_dashboard(
    *,
    issue_count: int,
    readable_news_keys: set[str],
    qualified_opportunity_count: int,
) -> list[str]:
    readable_news_count = len(readable_news_keys)
    held_categories = [ko for key, ko in REQUIRED_CATEGORY_ORDER if key not in readable_news_keys]
    total_readable_cards = issue_count + readable_news_count + qualified_opportunity_count
    action_parts: list[str] = []
    if issue_count:
        action_parts.append(f"주요 이슈 원문 확인 {issue_count}건")
    if readable_news_count:
        action_parts.append(f"뉴스 원문 확인 {readable_news_count}건")
    if qualified_opportunity_count:
        action_parts.append(f"신청 가능 공고 검토 {qualified_opportunity_count}건")
    if not action_parts:
        action_parts.append("오늘 즉시 처리할 확정 액션 없음")
    held_text = ", ".join(held_categories) if held_categories else "없음"
    return [
        "### 독자 대시보드",
        "",
        f"- 오늘 실제로 읽을 카드: {total_readable_cards}개 (주요 이슈 {issue_count}개, 원문 확인 뉴스 {readable_news_count}개, 신청 가능 공고 {qualified_opportunity_count}개).",
        f"- 보류된 뉴스 카테고리: {len(held_categories)}개 — {held_text}.",
        f"- 즉시 확인 액션: {len(action_parts) if action_parts[0] != '오늘 즉시 처리할 확정 액션 없음' else 0}개 — {', '.join(action_parts)}.",
        "",
    ]


def _render_category_briefing(news_items: Iterable[dict[str, object]], report_date: str) -> list[str]:
    grouped = _group_news_items(news_items)
    lines = ["## 뉴스 카테고리별 브리핑", "", "카테고리별 항목은 제목 나열이 아니라 원문 본문/요약에서 확인되는 실제 내용을 브리핑합니다. 본문·요약이 없는 제목만의 입력은 보류합니다.", ""]
    for category_key, ko in REQUIRED_CATEGORY_ORDER:
        bucket = [item for item in grouped.get(category_key, []) if _news_source_content(item)][:3]
        lines.extend([f"### {ko}"])
        if bucket:
            first = bucket[0]
            url = str(first.get("url") or "https://news.google.com/")
            source_content = _news_source_content(first)
            provider = _safe_text(first.get("provider"), "news")
            source = _safe_text(first.get("source") or first.get("site"), provider)
            source_link = _markdown_link(source, url)
            brief = _extract_article_brief(source_content, source)
            lines.extend(
                [
                    "- 출처 성격: 보도.",
                    f"- 확인된 사실: {brief.fact}",
                    f"- 왜 중요한가: {_grounded_why(brief.why_seed)}",
                    f"- 오늘 할 일: {_grounded_action(source, brief.action_focus)}",
                    f"- 근거: {provider} / {source_link} / {first.get('published_at') or report_date} / hash {str(first.get('content_hash') or '')[:12] or 'n/a'}",
                    "- 불확실성: 자동 추출 요약이므로 실제 수치·인용·맥락은 원문 본문으로 재확인해야 합니다.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "- 출처 성격: 보도.",
                    f"- 확인된 사실: {ko} 분야에서 오늘 보고에 올릴 만큼 원문 내용이 확인된 항목이 없습니다.",
                    "- 왜 중요한가: 근거가 약한 제목 나열을 이슈처럼 보이게 만들지 않기 위한 품질 제한입니다.",
                    "- 오늘 할 일: 관련 공식 발표와 보도 원문에서 날짜, 주체, 핵심 수치, 적용 대상을 확인한 항목만 다음 리포트에 올립니다.",
                    f"- 근거: {_markdown_link('뉴스 검색 링크', 'https://news.google.com/')}, {report_date} 확인.",
                    "- 불확실성: 이 공백은 실제 이슈 부재가 아니라 아직 원문 내용이 확인되지 않은 상태일 수 있습니다.",
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
    news_body_fetcher: Callable[[str], str] | None = None,
) -> UnifiedDailyReport:
    news_items_list = _enrich_news_items_for_briefing(news_items, body_fetcher=news_body_fetcher)
    opportunity_list = list(opportunity_candidates)
    issue_cards = _extract_issue_cards(hot_issue_markdown, report_date)
    issue_count = _issue_card_count(issue_cards)
    readable_news_keys = _readable_news_category_keys(news_items_list)
    qualified_count = sum(1 for item in opportunity_list if _opportunity_status(item)[0] == "신청 가능")
    if issue_count == 0 and not readable_news_keys and qualified_count == 0:
        raise ValueError("main issue section has no reader-facing issue cards and no verified fallback briefing")
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
        "- 해석 원칙: 이 보고서는 참고용 브리핑이며 원문 확인 전 확정 사실로 보지 않습니다.",
        "- 구성 원칙: 오늘 실제로 집중할 변화만 먼저 보여주고, 근거가 약한 항목은 아래 브리핑에서 보류합니다.",
        "",
        "## 한눈에 보기",
        "",
        "오늘 집중할 것:",
        *[f"- {card[0].removeprefix('### ').strip()}" for card in issue_cards[:3]],
        *([] if issue_cards else ["- 확인된 핵심 핫이슈 없음 — 뉴스 브리핑만 보조로 확인합니다."]),
        "",
        "## 오늘의 체크리스트",
        "",
        "- 오늘 확인: 주요 이슈 원문에서 실제 공개 범위, 릴리스 상태, 적용 대상을 확인합니다.",
        "- 이번 주 확인: 뉴스 브리핑의 수치·조건·정책 변화는 원문과 공식 발표가 일치하는 항목만 추적합니다.",
        "- 보류: 공식 상세 URL·마감·자격·지원내용이 모두 확인되지 않은 개인 기회는 신청 행동으로 올리지 않습니다.",
        "",
        "## 주요 이슈",
        "",
    ]
    if issue_cards:
        for card in issue_cards:
            lines.extend(card)
    else:
        lines.extend(
            [
                "- 승격된 주요 이슈 없음: 원문 내용과 독자 행동 근거가 충분한 항목이 없어 이 섹션은 비워 두고, 확인 가능한 뉴스 브리핑만 제공합니다.",
                "",
            ]
        )
    lines.extend(_render_opportunities(opportunity_list))
    lines.extend(_render_category_briefing(news_items_list, report_date))
    lines.extend(
        [
            "## 근거 커버리지",
            "",
            f"- 주요 이슈 카드: {issue_count}개",
            f"- 뉴스 입력 항목: {len(news_items_list)}개",
            f"- 개인 기회 입력: {len(opportunity_list)}개",
            f"- 필수 카테고리: {', '.join(ko for _, ko in REQUIRED_CATEGORY_ORDER)}",
            "- 확인 원칙: 원문 근거가 없는 항목은 행동 가능 또는 확정 사실로 보지 않습니다.",
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
    main_issue_body = _section_body(markdown, "주요 이슈")
    if not re.search(r"^###\s+", main_issue_body, flags=re.M) and "승격된 주요 이슈 없음" not in main_issue_body:
        errors.append("main issue section has no reader-facing issue cards")
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_daily_hot_issues_delivery_gate_module():
    script = _repo_root() / "scripts" / "gate_daily_hot_issues_delivery.py"
    spec = importlib.util.spec_from_file_location("gate_daily_hot_issues_delivery", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Daily Hot Issues delivery gate: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_daily_hot_issues_delivery_gate(markdown: Path, *, pdf: Path):
    """Run the reader-facing Daily Hot Issues gate for the generated artifact pair."""
    gate = _load_daily_hot_issues_delivery_gate_module()
    return gate.run_delivery_gate(Path(markdown), pdf=Path(pdf))


def _delivery_gate_result_dict(result) -> dict[str, object]:
    return {
        "ok": bool(result.ok),
        "failed_stage": result.failed_stage,
        "errors": list(result.errors),
        "markdown_path": str(result.markdown),
        "pdf_path": str(result.pdf),
        "html_path": str(result.html) if result.html else "",
        "text_path": str(result.text) if result.text else "",
        "pdfinfo": result.pdfinfo,
    }


def _remove_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _replace_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)


def _pending_path(path: Path) -> Path:
    return path.with_name(f".{path.stem}.pending{path.suffix}")


def write_unified_daily_report(
    *,
    report_date: str,
    hot_issue_markdown: str = "",
    news_items: Iterable[dict[str, object]] = (),
    opportunity_candidates: Iterable[OpportunityCandidate] = (),
    wiki_root: Path,
    workspace_root: Path,
    delivery_gate: bool = True,
) -> dict[str, object]:
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
    result: dict[str, object] = {
        "markdown_path": str(markdown_path),
        "pdf_path": str(pdf_path),
        "report_date": report_date,
        "news_item_count": len(news_items_list),
        "opportunity_candidate_count": len(opportunity_list),
    }
    if delivery_gate:
        pending_markdown_path = _pending_path(markdown_path)
        pending_pdf_path = _pending_path(pdf_path)
        pending_html_path = pending_pdf_path.with_suffix(".html")
        pending_text_path = pending_pdf_path.with_suffix(".txt")
        for stale_path in (pending_markdown_path, pending_pdf_path, pending_html_path, pending_text_path):
            _remove_if_exists(stale_path)
        pending_markdown_path.write_text(report.markdown, encoding="utf-8")
        raw_gate_result = run_daily_hot_issues_delivery_gate(pending_markdown_path, pdf=pending_pdf_path)
        gate_result = _delivery_gate_result_dict(raw_gate_result)
        if not gate_result["ok"]:
            for pending_path in (pending_markdown_path, pending_pdf_path, pending_html_path, pending_text_path):
                _remove_if_exists(pending_path)
            raise DeliveryGateError(gate_result)
        pending_markdown_path.replace(markdown_path)
        _replace_if_exists(pending_pdf_path, pdf_path)
        final_html_path = pdf_path.with_suffix(".html")
        final_text_path = pdf_path.with_suffix(".txt")
        _replace_if_exists(pending_html_path, final_html_path)
        _replace_if_exists(pending_text_path, final_text_path)
        gate_result["markdown_path"] = str(markdown_path)
        gate_result["pdf_path"] = str(pdf_path)
        gate_result["html_path"] = str(final_html_path) if final_html_path.exists() else ""
        gate_result["text_path"] = str(final_text_path) if final_text_path.exists() else ""
        result["delivery_gate"] = gate_result
    else:
        markdown_path.write_text(report.markdown, encoding="utf-8")
    return result


def generate_unified_daily_report(
    *,
    report_date: str,
    wiki_root: Path,
    workspace_root: Path,
    hot_issue_path: Path | None = None,
    news_json_path: Path | None = None,
    opportunity_json_path: Path | None = None,
    delivery_gate: bool = True,
) -> dict[str, object]:
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
        delivery_gate=delivery_gate,
    )
