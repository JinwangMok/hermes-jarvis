from __future__ import annotations

from .news_crawlers import (
    CATEGORY_KO,
    DEFAULT_CATEGORIES,
    DEFAULT_GOOGLE_QUERIES,
    NAVER_SID_BY_CATEGORY,
    append_news_center_to_daily_report,
    collect_news_center,
    generate_podcast_script,
    parse_google_news_rss as _parse_google_news_rss_articles,
    parse_naver_section_html as _parse_naver_section_html_articles,
    _google_rss_url,
    _naver_section_url,
)
from .news_crawlers.collector import _dedupe_items


def parse_google_news_rss(xml_text: str, *, category: str, scope: str, limit: int = 5) -> list[dict]:
    return [article.to_dict() for article in _parse_google_news_rss_articles(xml_text, category=category, scope=scope, limit=limit)]


def parse_naver_section_html(html_text: str, *, category: str, scope: str = "domestic", limit: int = 5) -> list[dict]:
    return [article.to_dict() for article in _parse_naver_section_html_articles(html_text, category=category, scope=scope, limit=limit)]

__all__ = [
    "CATEGORY_KO",
    "DEFAULT_CATEGORIES",
    "DEFAULT_GOOGLE_QUERIES",
    "NAVER_SID_BY_CATEGORY",
    "append_news_center_to_daily_report",
    "collect_news_center",
    "generate_podcast_script",
    "parse_google_news_rss",
    "parse_naver_section_html",
    "_dedupe_items",
    "_google_rss_url",
    "_naver_section_url",
]
