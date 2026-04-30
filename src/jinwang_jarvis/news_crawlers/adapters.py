from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser

from .models import Article, canonicalize_url, clean_text, make_article


def _strip_google_source_suffix(title: str) -> str:
    parts = title.rsplit(" - ", 1)
    return parts[0].strip() if len(parts) == 2 else title.strip()


def _infer_language(text: str) -> str:
    return "ko" if re.search(r"[가-힣]", text or "") else "en"


def _parse_dt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return clean_text(value)


def parse_google_news_rss(xml_text: str, *, category: str, scope: str, limit: int = 5) -> list[Article]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"malformed Google News RSS: {exc}") from exc
    articles: list[Article] = []
    for node in root.findall(".//item"):
        title = _strip_google_source_suffix(clean_text(node.findtext("title") or ""))
        url = clean_text(node.findtext("link") or "")
        summary = clean_text(unescape(node.findtext("description") or ""))
        source_node = node.find("source")
        site = clean_text(source_node.text if source_node is not None and source_node.text else "Google News")
        published_at = _parse_dt(node.findtext("pubDate") or "")
        guid = clean_text(node.findtext("guid") or "")
        if not title or not url:
            continue
        articles.append(
            make_article(
                provider="google-news",
                site=site,
                url=url,
                canonical_url=url,
                dedupe_key=canonicalize_url(url) or guid,
                title=title,
                published_at=published_at,
                category=category,
                scope=scope,
                summary=summary[:500],
                body_text=None,
                language=_infer_language(f"{title} {summary}"),
                fetch_status="ok",
                parse_status="metadata",
                source_quality=0.65,
            )
        )
        if len(articles) >= limit:
            break
    return articles


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
            title = clean_text(" ".join(self._chunks))
            if title:
                self.links.append((self._href, title))
            self._href = None
            self._chunks = []


def parse_naver_section_html(html_text: str, *, category: str, scope: str = "domestic", limit: int = 5) -> list[Article]:
    parser = _NaverLinkParser()
    parser.feed(html_text)
    articles: list[Article] = []
    seen_urls: set[str] = set()
    allowed_url_markers = ("n.news.naver.com/mnews/article/", "news.naver.com/main/read.naver", "news.naver.com/article/")
    for url, title in parser.links:
        if len(title) < 4 or "�" in title or title in {"동영상기사", "포토뉴스", "속보"}:
            continue
        if not any(marker in url for marker in allowed_url_markers):
            continue
        canonical = canonicalize_url(url)
        if canonical in seen_urls:
            continue
        seen_urls.add(canonical)
        articles.append(
            make_article(
                provider="naver-news",
                site="Naver News",
                url=url,
                canonical_url=canonical,
                dedupe_key=canonical,
                title=title,
                published_at=None,
                category=category,
                scope=scope,
                summary=title,
                body_text=None,
                language="ko",
                fetch_status="ok",
                parse_status="metadata",
                source_quality=0.55,
            )
        )
        if len(articles) >= limit:
            break
    return articles


@dataclass(frozen=True)
class ExtractedArticleBody:
    canonical_url: str
    title: str | None
    body_text: str


class _ArticleBodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonical_url: str | None = None
        self.title: str | None = None
        self._title_chunks: list[str] = []
        self._capture_title = False
        self._skip_depth = 0
        self._content_depth = 0
        self._paragraph_depth = 0
        self._paragraph_chunks: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value for key, value in attrs if key}
        tag = tag.lower()
        if tag == "link" and (attr_map.get("rel") or "").lower() == "canonical" and attr_map.get("href"):
            self.canonical_url = attr_map["href"]
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"}:
            self._skip_depth += 1
            return
        if tag == "title" and not self.title:
            self._capture_title = True
            self._title_chunks = []
        if tag in {"article", "main"} or attr_map.get("itemprop") == "articleBody":
            self._content_depth += 1
        if tag in {"p", "h1", "h2"} and self._skip_depth == 0:
            self._paragraph_depth += 1
            self._paragraph_chunks = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._capture_title:
            self._title_chunks.append(data)
        if self._paragraph_depth and (self._content_depth or len(data.strip()) >= 40):
            self._paragraph_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title" and self._capture_title:
            self.title = clean_text(" ".join(self._title_chunks)) or None
            self._capture_title = False
        if tag in {"p", "h1", "h2"} and self._paragraph_depth:
            text = clean_text(" ".join(self._paragraph_chunks))
            if len(text) >= 25:
                self.paragraphs.append(text)
            self._paragraph_depth -= 1
            self._paragraph_chunks = []
        if tag in {"article", "main"} and self._content_depth:
            self._content_depth -= 1


def extract_article_body(html_text: str, *, url: str) -> ExtractedArticleBody | None:
    parser = _ArticleBodyParser()
    try:
        parser.feed(html_text)
    except Exception:
        return None
    paragraphs = []
    seen: set[str] = set()
    for paragraph in parser.paragraphs:
        key = paragraph.casefold()
        if key in seen:
            continue
        seen.add(key)
        paragraphs.append(paragraph)
    body = clean_text("\n\n".join(paragraphs))
    if len(body) < 140 or len(paragraphs) < 2:
        return None
    return ExtractedArticleBody(canonical_url=canonicalize_url(parser.canonical_url or url, base_url=url), title=parser.title, body_text=body[:6000])


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
