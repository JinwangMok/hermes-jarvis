from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable

import yaml

from .wiki_contract import render_generated_report_frontmatter, write_markdown

Fetcher = Callable[[str], str]

DEFAULT_CATEGORIES = (
    {"internal_category": "politics", "korean_name": "정치", "naver_sid": "100"},
    {"internal_category": "economy", "korean_name": "경제", "naver_sid": "101"},
    {"internal_category": "society", "korean_name": "사회", "naver_sid": "102"},
    {"internal_category": "culture", "korean_name": "문화", "naver_sid": "103"},
    {"internal_category": "world", "korean_name": "국제", "naver_sid": "104"},
    {"internal_category": "technology", "korean_name": "기술", "naver_sid": "105"},
    {"internal_category": "entertainment", "korean_name": "예능", "naver_sid": "106"},
)

CATEGORY_KO = {
    "politics": "정치",
    "economy": "경제",
    "society": "사회",
    "culture": "문화",
    "world": "국제",
    "technology": "기술",
    "it-science": "기술",
    "entertainment": "예능",
}

NAVER_SID_BY_CATEGORY = {
    "politics": "100",
    "economy": "101",
    "society": "102",
    "culture": "103",
    "world": "104",
    "technology": "105",
    "it-science": "105",
    "entertainment": "106",
}

DEFAULT_GOOGLE_QUERIES = {
    "politics": {"domestic": ["한국 정치 주요 이슈"], "international": ["global politics major issue"]},
    "economy": {"domestic": ["한국 경제 주요 이슈"], "international": ["global economy major issue"]},
    "society": {"domestic": ["한국 사회 주요 이슈"], "international": ["global society major issue"]},
    "culture": {"domestic": ["한국 문화 주요 이슈"], "international": ["global culture major issue"]},
    "world": {"domestic": ["한국 외교 안보 주요 이슈"], "international": ["international breaking news"]},
    "technology": {"domestic": ["한국 AI 반도체 기술 뉴스"], "international": ["AI cloud semiconductor technology news"]},
    "it-science": {"domestic": ["한국 AI 반도체 기술 뉴스"], "international": ["AI cloud semiconductor technology news"]},
    "entertainment": {"domestic": ["한국 연예 방송 주요 이슈"], "international": ["global entertainment major issue"]},
}


def _default_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "jinwang-jarvis-news-center/0.1"})
    with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310 - curated public news URLs only
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_google_source_suffix(title: str) -> str:
    # Google News RSS commonly emits "headline - Publisher". Keep the headline.
    parts = title.rsplit(" - ", 1)
    return parts[0].strip() if len(parts) == 2 else title.strip()


def _normalized_title_key(title: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", title or "").casefold()


def _dedupe_items(items: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        url_key = (item.get("url") or "").strip()
        title_key = _normalized_title_key(str(item.get("title") or ""))
        category_scope = f"{item.get('category', '')}:{item.get('scope', '')}"
        title_dedupe_key = f"title:{category_scope}:{title_key}" if title_key else ""
        key_candidates = [key for key in (url_key, title_dedupe_key) if key]
        if not key_candidates or any(key in seen for key in key_candidates):
            continue
        seen.update(key_candidates)
        result.append(item)
    return result


def parse_google_news_rss(xml_text: str, *, category: str, scope: str, limit: int = 5) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"malformed Google News RSS: {exc}") from exc
    items: list[dict] = []
    for node in root.findall(".//item"):
        title = _strip_google_source_suffix(_clean_text(node.findtext("title") or ""))
        url = _clean_text(node.findtext("link") or "")
        summary = _clean_text(node.findtext("description") or "")
        source_node = node.find("source")
        source = _clean_text(source_node.text if source_node is not None and source_node.text else "Google News")
        published_at = _clean_text(node.findtext("pubDate") or "")
        if not title or not url:
            continue
        items.append(
            {
                "provider": "google-news",
                "category": category,
                "scope": scope,
                "title": title,
                "url": url,
                "source": source,
                "published_at": published_at,
                "summary": summary[:500],
            }
        )
        if len(items) >= limit:
            break
    return items


class _NaverLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._chunks: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href and ("news.naver.com" in href or "n.news.naver.com" in href):
            self._href = href
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            title = _clean_text(" ".join(self._chunks))
            if title:
                self.links.append((self._href, title))
            self._href = None
            self._chunks = []


def parse_naver_section_html(html_text: str, *, category: str, scope: str = "domestic", limit: int = 5) -> list[dict]:
    parser = _NaverLinkParser()
    parser.feed(html_text)
    items: list[dict] = []
    allowed_url_markers = ("n.news.naver.com/mnews/article/", "news.naver.com/main/read.naver", "news.naver.com/article/")
    for url, title in parser.links:
        if len(title) < 4 or "�" in title or title in {"동영상기사", "포토뉴스", "속보"}:
            continue
        if not any(marker in url for marker in allowed_url_markers):
            continue
        items.append(
            {
                "provider": "naver-news",
                "category": category,
                "scope": scope,
                "title": title,
                "url": url,
                "source": "네이버 뉴스",
                "published_at": "",
                "summary": title,
            }
        )
        if len(items) >= limit:
            break
    return _dedupe_items(items)


def _google_rss_url(query: str, *, scope: str = "domestic", hl: str | None = None, gl: str | None = None, ceid: str | None = None) -> str:
    if scope == "international":
        hl = hl or "en-US"
        gl = gl or "US"
        ceid = ceid or "US:en"
    else:
        hl = hl or "ko"
        gl = gl or "KR"
        ceid = ceid or "KR:ko"
    bounded_query = query if "when:" in query else f"{query} when:2d"
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": bounded_query, "hl": hl, "gl": gl, "ceid": ceid})


def _naver_section_url(sid: str) -> str:
    return f"https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1={sid}"


def _load_taxonomy(path: Path) -> dict:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if data.get("categories"):
            return data
    return {"version": "default", "categories": list(DEFAULT_CATEGORIES)}


def _category_specs(taxonomy: dict) -> list[dict]:
    specs: list[dict] = []
    for raw in taxonomy.get("categories", DEFAULT_CATEGORIES):
        category = str(raw.get("internal_category") or raw.get("naver_id") or "general").replace("_", "-")
        canonical = "technology" if category in {"it-science", "it_science"} else category
        ko = str(raw.get("korean_name") or CATEGORY_KO.get(canonical, canonical))
        naver_sid = str(raw.get("naver_sid") or NAVER_SID_BY_CATEGORY.get(canonical, "100"))
        google_queries = raw.get("google_queries") or DEFAULT_GOOGLE_QUERIES.get(canonical, DEFAULT_GOOGLE_QUERIES["politics"])
        specs.append({"category": canonical, "korean_name": ko, "naver_sid": naver_sid, "google_queries": google_queries})
    # user-requested explicit entertainment category may not exist in old taxonomy
    if not any(spec["category"] == "entertainment" for spec in specs):
        specs.append({"category": "entertainment", "korean_name": "예능", "naver_sid": "106", "google_queries": DEFAULT_GOOGLE_QUERIES["entertainment"]})
    return specs


def _summarize_item(item: dict) -> str:
    summary = _clean_text(str(item.get("summary") or item.get("title") or ""))
    if not summary:
        return "제목과 출처만 확인됨. 원문 확인 필요."
    return summary[:220]


def _render_news_markdown(items: list[dict], *, generated_day: str, title: str = "뉴스 센터 브리핑") -> str:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        grouped.setdefault((item["category"], item["scope"]), []).append(item)
    lines = [f"## {title}", "", "네이버 뉴스와 구글 뉴스에서 수집한 메타데이터·요약 기반 보강 섹션입니다. 최종 판단 전 원문을 확인합니다.", ""]
    scope_label = {"domestic": "국내", "international": "국외"}
    for category in sorted({key[0] for key in grouped.keys()}):
        for scope in ("domestic", "international"):
            bucket = grouped.get((category, scope), [])
            if not bucket:
                continue
            ko = CATEGORY_KO.get(category, category)
            lines.extend([f"### {ko} · {scope_label.get(scope, scope)}", ""])
            for item in bucket[:4]:
                lines.extend(
                    [
                        f"- 확인된 사실: {item['title']} — {_summarize_item(item)}",
                        f"- 왜 중요한가: {ko} 영역의 오늘 주요 흐름을 파악하기 위한 참고 기사입니다.",
                        f"- 오늘 할 일: [{item.get('source') or item['provider']}]({item['url']}) 원문에서 세부 사실과 날짜를 확인합니다.",
                        f"- 근거: {item['provider']} / {item.get('published_at') or generated_day}",
                        "- 불확실성: 자동 수집 요약이므로 제목과 요약만으로 단정하지 않습니다.",
                        "",
                    ]
                )
    return "\n".join(lines).strip() + "\n"


def collect_news_center(
    *,
    taxonomy_path: Path,
    output_dir: Path,
    wiki_root: Path,
    fetcher: Fetcher | None = None,
    now_iso: str | None = None,
    per_source_limit: int = 5,
) -> dict:
    fetch = fetcher or _default_fetch
    if per_source_limit < 1:
        raise ValueError("per_source_limit must be >= 1")
    now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc).astimezone()
    generated_day = now.date().isoformat()
    taxonomy = _load_taxonomy(taxonomy_path)
    specs = _category_specs(taxonomy)
    errors: list[dict] = []
    items: list[dict] = []

    for spec in specs:
        category = spec["category"]
        try:
            items.extend(parse_naver_section_html(fetch(_naver_section_url(spec["naver_sid"])), category=category, scope="domestic", limit=per_source_limit))
        except Exception as exc:  # network must not kill the daily report
            errors.append({"provider": "naver-news", "category": category, "error": str(exc)})
        google_queries = spec.get("google_queries") or {}
        for scope in ("domestic", "international"):
            for query in google_queries.get(scope, [])[:2]:
                try:
                    items.extend(parse_google_news_rss(fetch(_google_rss_url(str(query), scope=scope)), category=category, scope=scope, limit=per_source_limit))
                except Exception as exc:
                    errors.append({"provider": "google-news", "category": category, "scope": scope, "query": str(query), "error": str(exc)})

    items = _dedupe_items(items)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%S%z")
    artifact_path = output_dir / f"news-center-{stamp}.json"
    md_path = output_dir / f"news-center-{stamp}.md"
    payload = {"generated_at": now.isoformat(), "taxonomy_path": str(taxonomy_path), "items": items, "errors": errors}
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    news_md = _render_news_markdown(items, generated_day=generated_day)
    md_path.write_text(news_md, encoding="utf-8")

    daily_page = wiki_root / "reports/news-center/daily" / f"{generated_day}.md"
    daily_lines = render_generated_report_frontmatter(
        title=f"News Center Daily {generated_day}",
        date=generated_day,
        subtype="generated-daily-report",
        tags=["jarvis", "intelligence", "report", "daily", "hot-issues"],
        operational_source_of_truth=str(artifact_path),
        summary="Naver/Google News category briefing",
        refresh_policy="daily-snapshot",
    )
    daily_lines.extend([f"# 뉴스 센터 Daily — {generated_day}", "", news_md])
    write_markdown(daily_page, daily_lines)

    for category in sorted({item["category"] for item in items}):
        category_items = [item for item in items if item["category"] == category]
        category_page = wiki_root / "reports/news-center/categories" / f"{category}.md"
        category_lines = render_generated_report_frontmatter(
            title=f"News Center Category — {CATEGORY_KO.get(category, category)}",
            date=generated_day,
            subtype="category-shard",
            tags=["jarvis", "intelligence", "report", "daily"],
            operational_source_of_truth=str(artifact_path),
            summary=f"Naver/Google News category shard for {category}",
        )
        category_lines.extend([f"# 뉴스 센터 카테고리 — {CATEGORY_KO.get(category, category)}", "", _render_news_markdown(category_items, generated_day=generated_day, title="카테고리별 핵심 뉴스")])
        write_markdown(category_page, category_lines)

    return {
        "artifact_path": str(artifact_path),
        "markdown_path": str(md_path),
        "wiki_daily_path": str(daily_page),
        "item_count": len(items),
        "error_count": len(errors),
        "news_markdown": news_md,
    }


def append_news_center_to_daily_report(daily_report_path: Path, news_markdown: str) -> None:
    text = daily_report_path.read_text(encoding="utf-8") if daily_report_path.exists() else ""
    cleaned = news_markdown.strip() + "\n"
    pattern = re.compile(r"\n## 뉴스(?: 센터)? 브리핑\n.*?(?=\n## |\Z)", re.S)
    if pattern.search(text):
        text = pattern.sub("\n" + cleaned, text, count=1)
    else:
        text = text.rstrip() + "\n\n" + cleaned
    daily_report_path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _extract_podcast_items(report_text: str, max_items: int) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in report_text.splitlines():
        if line.startswith("### "):
            if current_title and current_lines:
                items.append((current_title, " ".join(current_lines)))
            current_title = line[4:].strip()
            current_lines = []
        elif current_title and ("확인된 내용:" in line or "확인된 사실:" in line or "왜 중요한가:" in line or "오늘 할 일:" in line):
            current_lines.append(line.lstrip("- ").strip())
    if current_title and current_lines:
        items.append((current_title, " ".join(current_lines)))
    return items[:max_items]


def _tts_safe_text(text: str) -> str:
    text = re.sub(r"\[[^\]]+\]\([^\)]+\)", lambda m: m.group(0).split("]", 1)[0].lstrip("["), text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\b(확인된 사실|확인된 내용)\s*:\s*", "", text)
    text = re.sub(r"\b왜 중요한가\s*:\s*", " 이 내용이 중요한 이유는 ", text)
    text = re.sub(r"\b오늘 할 일\s*:\s*", " 오늘 할 일은 ", text)
    text = re.sub(r"\b근거\s*:\s*", " 근거는 ", text)
    text = re.sub(r"\b불확실성\s*:\s*", " 다만 ", text)
    text = re.sub(r"\s+", " ", text)
    return _clean_text(text).strip()


def generate_podcast_script(daily_report_path: Path, *, output_path: Path, max_items: int = 8) -> dict:
    report_text = daily_report_path.read_text(encoding="utf-8")
    items = _extract_podcast_items(report_text, max_items=max_items)
    lines = [
        "# TTS용 팟캐스트 스크립트",
        "",
        "진행자 A: 안녕하세요. 오늘의 핫이슈를 짧게 정리해드립니다.",
        "진행자 B: 네. 제목만 훑지 않고, 확인된 내용과 오늘 할 일을 중심으로 보겠습니다.",
        "",
    ]
    if not items:
        lines.append("진행자 A: 오늘은 팟캐스트로 풀어낼 만큼 구조화된 뉴스 항목이 아직 없습니다.")
    for index, (title, body) in enumerate(items, start=1):
        lines.extend(
            [
                f"진행자 A: {index}번째입니다. {title}.",
                f"진행자 B: 핵심은 이렇습니다. {_tts_safe_text(body)[:520]}",
                "진행자 A: 따라서 오늘은 원문 확인과 후속 일정 여부만 체크하고, 확인되지 않은 부분은 단정하지 않겠습니다.",
                "",
            ]
        )
    lines.extend([
        "진행자 B: 여기까지입니다. 자세한 링크와 근거는 PDF 리포트에서 확인하세요.",
        "진행자 A: 이상, 자비스 데일리 브리핑이었습니다.",
    ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"script_path": str(output_path), "item_count": len(items)}
