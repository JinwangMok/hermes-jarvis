from __future__ import annotations

import json
from pathlib import Path

from jinwang_jarvis.news_center import (
    _dedupe_items,
    _google_rss_url,
    append_news_center_to_daily_report,
    collect_news_center,
    generate_podcast_script,
    parse_google_news_rss,
    parse_naver_section_html,
)


def test_parse_google_news_rss_normalizes_category_and_scope() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel>
      <item>
        <title>AI 반도체 수출 통제 확대 - Example</title>
        <link>https://news.google.com/rss/articles/abc</link>
        <source url="https://example.com">Example</source>
        <pubDate>Sun, 26 Apr 2026 01:00:00 GMT</pubDate>
        <description>정부가 AI 반도체 수출 통제를 확대했다.</description>
      </item>
    </channel></rss>
    """

    items = parse_google_news_rss(xml, category="technology", scope="international", limit=3)

    assert len(items) == 1
    assert items[0]["provider"] == "google-news"
    assert items[0]["category"] == "technology"
    assert items[0]["scope"] == "international"
    assert items[0]["title"] == "AI 반도체 수출 통제 확대"
    assert items[0]["source"] == "Example"
    assert items[0]["url"].startswith("https://news.google.com/")
    assert "수출 통제" in items[0]["summary"]


def test_parse_naver_section_html_extracts_metadata_only_items() -> None:
    html = """
    <html><body>
      <a href="https://n.news.naver.com/mnews/article/001/0000000001">여야, AI 기본법 후속 논의 착수</a>
      <a href="https://n.news.naver.com/mnews/article/002/0000000002">경제 뉴스</a>
      <a href="https://sports.news.naver.com">스포츠</a>
      <a href="https://news.naver.com/ombudsman/revisionArticleList">�������� ����</a>
      <a href="https://example.com/not-news">무시</a>
    </body></html>
    """

    items = parse_naver_section_html(html, category="politics", scope="domestic", limit=5)

    assert [item["provider"] for item in items] == ["naver-news", "naver-news"]
    assert items[0]["category"] == "politics"
    assert items[0]["scope"] == "domestic"
    assert items[0]["title"] == "여야, AI 기본법 후속 논의 착수"
    assert items[0]["url"].startswith("https://n.news.naver.com/")


def test_collect_news_center_writes_json_and_wiki_pages(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.yaml"
    taxonomy.write_text(
        """
version: test
collection_policy: metadata_only_with_excerpt
categories:
  - internal_category: politics
    korean_name: 정치
    naver_sid: '100'
    google_queries:
      domestic: ['한국 정치 AI 정책']
      international: ['global AI policy']
  - internal_category: technology
    korean_name: 기술
    naver_sid: '105'
    google_queries:
      domestic: ['한국 AI 반도체']
      international: ['AI semiconductor export controls']
""".strip(),
        encoding="utf-8",
    )
    wiki_root = tmp_path / "wiki"
    output_dir = tmp_path / "data" / "news-center"

    naver_html = """<a href="https://n.news.naver.com/mnews/article/001/1">국내 AI 정책 논의</a>"""

    def fake_fetch(url: str) -> str:
        if "news.naver.com" in url:
            return naver_html
        suffix = "intl" if "global" in url or "export" in url else "domestic"
        return f"""<rss><channel><item><title>AI 정책 발표 {suffix} - 언론사</title><link>https://news.google.com/rss/articles/{suffix}-{abs(hash(url))}</link><source>언론사</source><description>AI 정책 원문 요지 {suffix}</description></item></channel></rss>"""

    result = collect_news_center(
        taxonomy_path=taxonomy,
        output_dir=output_dir,
        wiki_root=wiki_root,
        fetcher=fake_fetch,
        now_iso="2026-04-26T10:00:00+09:00",
        per_source_limit=2,
    )

    assert result["item_count"] >= 4
    artifact = Path(result["artifact_path"])
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert {item["scope"] for item in payload["items"]} == {"domestic", "international"}
    assert (wiki_root / "reports/news-center/daily/2026-04-26.md").exists()
    category_page = (wiki_root / "reports/news-center/categories/politics.md").read_text(encoding="utf-8")
    assert "국내" in category_page and "국외" in category_page
    assert "확인된 사실" in category_page


def test_append_news_center_to_daily_report_is_idempotent(tmp_path: Path) -> None:
    daily = tmp_path / "daily.md"
    daily.write_text("# 오늘의 핫이슈\n\n## 주요 이슈\n본문\n", encoding="utf-8")
    news = "## 뉴스 센터 브리핑\n\n### 정치 · 국내\n- 확인된 사실: 핵심 내용"

    append_news_center_to_daily_report(daily, news)
    append_news_center_to_daily_report(daily, news)

    text = daily.read_text(encoding="utf-8")
    assert text.count("## 뉴스 센터 브리핑") == 1
    assert "정치 · 국내" in text


def test_append_news_center_replaces_legacy_heading_too(tmp_path: Path) -> None:
    daily = tmp_path / "daily.md"
    daily.write_text("# 오늘의 핫이슈\n\n## 뉴스 브리핑\nold\n\n## 주요 이슈\n본문\n", encoding="utf-8")
    news = "## 뉴스 센터 브리핑\n\n### 경제 · 국외\n- 확인된 사실: 새 내용"

    append_news_center_to_daily_report(daily, news)

    text = daily.read_text(encoding="utf-8")
    assert "## 뉴스 브리핑\nold" not in text
    assert text.count("## 뉴스 센터 브리핑") == 1
    assert "새 내용" in text


def test_google_international_url_uses_international_locale() -> None:
    url = _google_rss_url("global AI policy", scope="international")
    assert "ceid=US%3Aen" in url
    assert "hl=en-US" in url
    assert "gl=US" in url


def test_dedupe_items_uses_normalized_title_across_different_urls() -> None:
    items = [
        {"title": "AI 정책 발표!", "url": "https://a.example/1"},
        {"title": "AI 정책 발표", "url": "https://b.example/2"},
        {"title": "반도체 투자 확대", "url": "https://c.example/3"},
    ]
    deduped = _dedupe_items(items)
    assert [item["title"] for item in deduped] == ["AI 정책 발표!", "반도체 투자 확대"]


def test_collect_news_center_rejects_non_positive_limit(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.yaml"
    taxonomy.write_text("version: test\ncategories: []\n", encoding="utf-8")
    try:
        collect_news_center(taxonomy_path=taxonomy, output_dir=tmp_path / "out", wiki_root=tmp_path / "wiki", per_source_limit=0)
    except ValueError as exc:
        assert "per_source_limit" in str(exc)
    else:
        raise AssertionError("per_source_limit=0 should fail")


def test_malformed_google_rss_is_reported_as_source_error(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.yaml"
    taxonomy.write_text(
        """
version: test
categories:
  - internal_category: politics
    korean_name: 정치
    naver_sid: '100'
    google_queries:
      domestic: ['한국 정치']
      international: []
""".strip(),
        encoding="utf-8",
    )

    def fake_fetch(url: str) -> str:
        if "news.naver.com" in url:
            return "<a href='https://n.news.naver.com/mnews/article/001/1'>정치 기사</a>"
        return "<rss><broken>"

    result = collect_news_center(
        taxonomy_path=taxonomy,
        output_dir=tmp_path / "out",
        wiki_root=tmp_path / "wiki",
        fetcher=fake_fetch,
        now_iso="2026-04-26T10:00:00+09:00",
    )
    payload = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert result["error_count"] >= 1
    assert any(error["provider"] == "google-news" for error in payload["errors"])


def test_generate_podcast_script_uses_conversational_two_host_format(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text(
        "# 오늘의 핫이슈\n\n## 뉴스 브리핑\n### 정치 · 국내\n- 확인된 사실: 국회가 AI 법안을 논의했다.\n- 왜 중요한가: 연구 정책에 영향.\n- 오늘 할 일: 원문 확인.\n",
        encoding="utf-8",
    )
    output = tmp_path / "podcast.md"

    result = generate_podcast_script(report, output_path=output, max_items=3)

    script = output.read_text(encoding="utf-8")
    assert result["script_path"] == str(output)
    assert "진행자 A" in script and "진행자 B" in script
    assert "정치 · 국내" in script
    assert "TTS용 팟캐스트 스크립트" in script
    assert "http" not in script
    assert "확인된 사실:" not in script
