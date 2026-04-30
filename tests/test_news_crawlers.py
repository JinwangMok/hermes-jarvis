from __future__ import annotations

import json
from pathlib import Path

from jinwang_jarvis.news_crawlers import (
    Article,
    collect_news_center,
    extract_article_body,
    parse_google_news_rss,
    parse_naver_section_html,
)


GOOGLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item>
    <title>AI 반도체 투자 확대 - Example Daily</title>
    <link>https://news.google.com/rss/articles/abc?utm_source=x</link>
    <guid isPermaLink="false">CBMiabc</guid>
    <source url="https://example.com">Example Daily</source>
    <pubDate>Sun, 26 Apr 2026 01:00:00 GMT</pubDate>
    <description><![CDATA[정부가 <b>AI 반도체</b> 투자를 확대했다.]]></description>
  </item>
</channel></rss>
"""


def test_google_rss_adapter_returns_normalized_articles_with_hashes() -> None:
    articles = parse_google_news_rss(GOOGLE_RSS, category="technology", scope="domestic", limit=3)

    assert len(articles) == 1
    article = articles[0]
    assert isinstance(article, Article)
    assert article.provider == "google-news"
    assert article.site == "Example Daily"
    assert article.title == "AI 반도체 투자 확대"
    assert article.category == "technology"
    assert article.language == "ko"
    assert article.fetch_status == "ok"
    assert article.parse_status == "metadata"
    assert len(article.content_hash) == 64
    assert article.to_dict()["source"] == "Example Daily"


def test_naver_adapter_uses_section_links_and_taxonomy_category() -> None:
    html = """
    <html><body>
      <a href="https://n.news.naver.com/mnews/article/001/0000000001?sid=102">청년 주거 정책 지원 확대</a>
      <a href="https://news.naver.com/main/read.naver?oid=002&aid=0000000002">교육 노동 정책 논의</a>
      <a href="https://sports.news.naver.com/game">무시할 스포츠</a>
    </body></html>
    """

    articles = parse_naver_section_html(html, category="society", scope="domestic", limit=5)

    assert [article.provider for article in articles] == ["naver-news", "naver-news"]
    assert articles[0].category == "society"
    assert articles[0].site == "Naver News"
    assert articles[0].canonical_url.startswith("https://n.news.naver.com/mnews/article/001/0000000001")


def test_generic_html_extractor_is_conservative_and_ignores_navigation() -> None:
    html = """
    <html><head><link rel="canonical" href="https://example.com/canonical" /></head><body>
      <nav>login menu share subscribe</nav>
      <article>
        <h1>AI cloud policy</h1>
        <p>First paragraph has enough concrete article text about policy, cloud infrastructure, research funding, and public service impact.</p>
        <p>Second paragraph adds more deterministic body text so the extractor can safely treat this as an article body, not just boilerplate.</p>
      </article>
      <footer>copyright links</footer>
    </body></html>
    """

    extracted = extract_article_body(html, url="https://example.com/original")

    assert extracted is not None
    assert extracted.canonical_url == "https://example.com/canonical"
    assert "public service impact" in extracted.body_text
    assert "login menu" not in extracted.body_text


def test_generic_html_extractor_rejects_boilerplate_only_pages() -> None:
    assert extract_article_body("<html><body><nav>menu</nav><p>short</p></body></html>", url="https://example.com") is None


def test_collector_generated_markdown_uses_safer_crawled_report_label(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.yaml"
    taxonomy.write_text(
        """
version: test
categories:
  - internal_category: technology
    korean_name: 기술
    naver_sid: '105'
    google_queries:
      domestic: ['한국 AI 반도체']
      international: []
  - internal_category: entertainment
    korean_name: 예능
    naver_sid: '106'
    google_queries:
      domestic: []
      international: []
""".strip(),
        encoding="utf-8",
    )

    def fake_fetch(url: str) -> str:
        if "news.naver.com" in url:
            return "<html><body></body></html>"
        if "news.google.com" in url:
            return GOOGLE_RSS.replace("https://news.google.com/rss/articles/abc?utm_source=x", "https://example.com/metadata-only")
        return "<html><body><article><p>short</p></article></body></html>"

    result = collect_news_center(
        taxonomy_path=taxonomy,
        output_dir=tmp_path / "data" / "news-center",
        wiki_root=tmp_path / "wiki",
        fetcher=fake_fetch,
        now_iso="2026-04-26T10:00:00+09:00",
        per_source_limit=1,
    )

    assert "- 수집된 보도:" in result["news_markdown"]
    assert "- 확인된 사실:" not in result["news_markdown"]


def test_collector_enriches_article_body_when_extractor_succeeds(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.yaml"
    taxonomy.write_text(
        """
version: test
categories:
  - internal_category: technology
    korean_name: 기술
    naver_sid: '105'
    google_queries:
      domestic: ['한국 AI 반도체']
      international: []
  - internal_category: entertainment
    korean_name: 예능
    naver_sid: '106'
    google_queries:
      domestic: []
      international: []
""".strip(),
        encoding="utf-8",
    )
    article_url = "https://example.com/article?utm_source=feed"
    rss = GOOGLE_RSS.replace("https://news.google.com/rss/articles/abc?utm_source=x", article_url)
    article_body_fetches: list[str] = []

    def fake_fetch(url: str) -> str:
        if "news.naver.com" in url:
            return "<html><body></body></html>"
        if "news.google.com" in url:
            return rss
        article_body_fetches.append(url)
        return """
        <html><head><link rel="canonical" href="https://example.com/canonical?utm_source=body" /></head><body>
          <article>
            <h1>AI 반도체 투자 확대</h1>
            <p>First extracted paragraph contains enough article body detail about AI semiconductor investment, public cloud infrastructure, research funding, and procurement timing.</p>
            <p>Second extracted paragraph adds source-grounded context for readers while staying inside the mocked article body and avoiding any invented details outside the fetched HTML.</p>
          </article>
        </body></html>
        """

    result = collect_news_center(
        taxonomy_path=taxonomy,
        output_dir=tmp_path / "data" / "news-center",
        wiki_root=tmp_path / "wiki",
        fetcher=fake_fetch,
        now_iso="2026-04-26T10:00:00+09:00",
        per_source_limit=1,
    )
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    item = payload["items"][0]

    assert article_body_fetches == [article_url]
    assert item["canonical_url"] == "https://example.com/canonical"
    assert item["parse_status"] == "body_extracted"
    assert "source-grounded context" in item["body_text"]
    assert len(item["content_hash"]) == 64


def test_collector_keeps_metadata_only_when_body_extraction_returns_none(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.yaml"
    taxonomy.write_text(
        """
version: test
categories:
  - internal_category: technology
    korean_name: 기술
    naver_sid: '105'
    google_queries:
      domestic: ['한국 AI 반도체']
      international: []
  - internal_category: entertainment
    korean_name: 예능
    naver_sid: '106'
    google_queries:
      domestic: []
      international: []
""".strip(),
        encoding="utf-8",
    )
    article_url = "https://example.com/article"
    rss = GOOGLE_RSS.replace("https://news.google.com/rss/articles/abc?utm_source=x", article_url)

    def fake_fetch(url: str) -> str:
        if "news.naver.com" in url:
            return "<html><body></body></html>"
        if "news.google.com" in url:
            return rss
        return "<html><body><article><p>too short</p></article></body></html>"

    result = collect_news_center(
        taxonomy_path=taxonomy,
        output_dir=tmp_path / "data" / "news-center",
        wiki_root=tmp_path / "wiki",
        fetcher=fake_fetch,
        now_iso="2026-04-26T10:00:00+09:00",
        per_source_limit=1,
    )
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    item = payload["items"][0]

    assert item["canonical_url"] == article_url
    assert item["parse_status"] == "metadata"
    assert item["body_text"] is None
    assert item["summary"] == "정부가 AI 반도체 투자를 확대했다."


def test_collector_dedupes_hashes_and_skips_unchanged_generated_writes(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.yaml"
    taxonomy.write_text(
        """
version: test
categories:
  - internal_category: technology
    korean_name: 기술
    naver_sid: '105'
    google_queries:
      domestic: ['한국 AI 반도체']
      international: []
""".strip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "data" / "news-center"
    wiki_root = tmp_path / "wiki"
    google_xml = GOOGLE_RSS.replace("https://news.google.com/rss/articles/abc?utm_source=x", "https://example.com/same-story")

    def fake_fetch(url: str) -> str:
        if "news.naver.com" in url:
            return '<a href="https://n.news.naver.com/mnews/article/001/1">AI 반도체 투자 확대</a>'
        return google_xml

    first = collect_news_center(
        taxonomy_path=taxonomy,
        output_dir=output_dir,
        wiki_root=wiki_root,
        fetcher=fake_fetch,
        now_iso="2026-04-26T10:00:00+09:00",
        per_source_limit=2,
    )
    second = collect_news_center(
        taxonomy_path=taxonomy,
        output_dir=output_dir,
        wiki_root=wiki_root,
        fetcher=fake_fetch,
        now_iso="2026-04-26T10:00:00+09:00",
        per_source_limit=2,
    )

    payload = json.loads(Path(first["artifact_path"]).read_text(encoding="utf-8"))
    assert payload["metadata"]["collection_hash"] == second["collection_hash"]
    assert all(len(item["content_hash"]) == 64 for item in payload["items"])
    assert sum(1 for item in payload["items"] if item["category"] == "technology") == 1
    assert second["skipped_write_count"] >= 2
    latest_payload = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))
    assert latest_payload["metadata"]["skipped_write_count"] >= 1
    daily_page = wiki_root / "reports/news-center/daily/2026-04-26.md"
    assert daily_page.exists()
    assert "operational_source_of_truth" in daily_page.read_text(encoding="utf-8")
