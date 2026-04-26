import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinwang_jarvis.bootstrap import bootstrap_workspace
from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.watch import (
    WatchSource,
    build_watch_stories,
    collect_watch_signals,
    extract_x_status_id,
    fetch_source_items,
    generate_external_hot_issue_alert,
    generate_watch_report,
    judge_watch_issues,
    load_watch_sources,
    parse_x_status_metrics,
    sync_watch_sources,
)


RSS_SAMPLE = """<?xml version='1.0' encoding='UTF-8'?>
<rss version='2.0'>
  <channel>
    <title>OpenAI News</title>
    <item>
      <title>OpenAI launches new enterprise API tier</title>
      <link>https://openai.com/news/enterprise-api-tier</link>
      <description>official launch</description>
      <pubDate>Wed, 23 Apr 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

ATOM_SAMPLE = """<?xml version='1.0' encoding='utf-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <title>GeekNews</title>
  <entry>
    <title>OpenAI launches new enterprise API tier</title>
    <link href='https://news.hada.io/topic?id=123' />
    <summary>community reaction</summary>
    <updated>2026-04-23T00:10:00+00:00</updated>
    <id>tag:hada.io,2026:123</id>
  </entry>
</feed>
"""

NITTER_RSS_SAMPLE = """<?xml version='1.0' encoding='UTF-8'?>
<rss version='2.0'>
  <channel>
    <title>OpenAI / Nitter</title>
    <item>
      <title>OpenAI ships a new public model update</title>
      <link>https://nitter.net/OpenAI/status/1912345678901234567#m</link>
      <guid isPermaLink='true'>https://nitter.net/OpenAI/status/1912345678901234567#m</guid>
      <description>model update thread</description>
      <pubDate>Wed, 23 Apr 2026 00:05:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

X_STATUS_HTML_SAMPLE = """
<html><body>
<script>
{"reply_count":"42","retweet_count":"314","quote_count":"12","favorite_count":"1.5K"}
</script>
</body></html>
"""

JSON_FEED_SAMPLE = json.dumps({
    "items": [
        {
            "title": "Cisco expands cloud networking security",
            "link": "https://newsroom.cisco.com/news/cloud-security",
            "description": "Cisco announced cloud networking security updates for datacenter operators.",
            "pubDate": "Wed, 23 Apr 2026 00:00:00 GMT",
        }
    ]
})

ARTICLE_HTML_SAMPLE = """
<html><body>
<header>site navigation</header>
<article>
  <h1>Enterprise API tier</h1>
  <p>OpenAI introduced a new enterprise API tier with stronger compliance controls, higher throughput, and predictable procurement for large organizations.</p>
  <p>The announcement matters because it changes how companies can deploy frontier models in production cloud environments.</p>
</article>
</body></html>
"""

SEARCH_HTML_SAMPLE = """
<html><body>
  <a class="result__a" href="https://mirror.example.com/openai-enterprise-api-tier">OpenAI launches new enterprise API tier</a>
</body></html>
"""

MIRROR_ARTICLE_HTML_SAMPLE = """
<html><body>
<article>
  <p>A mirrored report says OpenAI's enterprise API tier adds audit controls, procurement guarantees, and deployment governance for regulated customers.</p>
  <p>This detail is enough to summarize the real substance even when the original URL blocks scraping.</p>
</article>
</body></html>
"""


def _write_config(tmp_path: Path) -> Path:
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(
        f"""
workspace_root: {tmp_path.as_posix()}
wiki_root: {tmp_path.as_posix()}/wiki
accounts: []
mail:
  snapshot_dir: data/snapshots/mail
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord:test
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: jinwang-jarvis
watch:
  enabled: true
  snapshot_dir: data/watch
  source_config_dir: config/watch-sources
  default_poll_minutes: 60
  adjudicator_model: gpt-5.4
  fallback_model: gpt-5.5
  importance_alert_threshold: 0.82
  momentum_alert_threshold: 0.18
  digest_threshold: 0.60
  recency_hours: 24
  story_similarity: 0.84
  compare_window_hours: 1
  target_companies: [openai]
  subreddits: [LocalLLaMA]
  enable_sources: {{}}
""",
        encoding="utf-8",
    )
    return config_file


def _recent_iso(*, minutes_ago: int = 0) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).replace(microsecond=0).isoformat()



def _write_sources(tmp_path: Path) -> None:
    base = tmp_path / "config/watch-sources"
    (base / "official").mkdir(parents=True, exist_ok=True)
    (base / "reaction").mkdir(parents=True, exist_ok=True)
    (base / "official/openai-news.yaml").write_text(
        """source_id: openai-news
display_name: OpenAI News RSS
company_tag: openai
source_class: company
source_role: official-origin
source_type: rss
ingest_strategy: rss
base_url: https://openai.com/news/
feed_url: https://openai.com/news/rss.xml
html_list_url: null
poll_minutes: 60
enabled: true
validation_status: verified
validation_notes: [ok]
browser_required: false
anti_bot_risk: low
priority_weight: 1.0
reaction_weight: 0.0
cooldown_minutes: 60
topic_tags: [ai-models, launch]
""",
        encoding="utf-8",
    )
    (base / "official/openai-x.yaml").write_text(
        """source_id: openai-x
display_name: OpenAI on X
company_tag: openai
source_class: company
source_role: official-origin
source_type: x
ingest_strategy: rss
base_url: https://x.com/OpenAI
feed_url: https://nitter.net/OpenAI/rss
html_list_url: null
poll_minutes: 30
enabled: true
validation_status: verified
validation_notes: [nitter-rss, x-html-metrics]
browser_required: false
anti_bot_risk: medium
priority_weight: 1.0
reaction_weight: 0.0
cooldown_minutes: 30
topic_tags: [ai-models, launch, social]
""",
        encoding="utf-8",
    )
    (base / "official/anthropic-news.yaml").write_text(
        """source_id: anthropic-news
display_name: Anthropic News
company_tag: anthropic
source_class: company
source_role: official-origin
source_type: html
ingest_strategy: html
base_url: https://www.anthropic.com/news
feed_url: null
html_list_url: https://www.anthropic.com/news
poll_minutes: 60
enabled: true
validation_status: partial
validation_notes: [ok]
browser_required: false
anti_bot_risk: medium
priority_weight: 1.0
reaction_weight: 0.0
cooldown_minutes: 60
topic_tags: [ai-models, launch]
""", encoding='utf-8')
    (base / "reaction/geeknews.yaml").write_text(
        """source_id: geeknews
display_name: GeekNews Feed
company_tag: null
source_class: community
source_role: reaction
source_type: atom
ingest_strategy: atom
base_url: https://news.hada.io/
feed_url: https://feeds.feedburner.com/geeknews-feed
html_list_url: null
poll_minutes: 60
enabled: true
validation_status: verified
validation_notes: [ok]
browser_required: false
anti_bot_risk: low
priority_weight: 0.0
reaction_weight: 1.0
cooldown_minutes: 60
topic_tags: [community]
""",
        encoding="utf-8",
    )
    (base / "reaction/hackernews.yaml").write_text(
        """source_id: hackernews-topstories
display_name: Hacker News Topstories API
company_tag: null
source_class: community
source_role: reaction
source_type: api
ingest_strategy: api
base_url: https://news.ycombinator.com/
feed_url: https://hacker-news.firebaseio.com/v0/topstories.json
html_list_url: null
poll_minutes: 60
enabled: true
validation_status: verified
validation_notes: [ok]
browser_required: false
anti_bot_risk: low
priority_weight: 0.0
reaction_weight: 1.0
cooldown_minutes: 60
topic_tags: [community, developer]
""",
        encoding="utf-8",
    )



def test_fetch_source_items_parses_rss_atom_html_api_and_x(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    _write_sources(tmp_path)
    sources = load_watch_sources(config)
    by_id = {source.source_id: source for source in sources}

    rss_items = fetch_source_items(
        by_id["openai-news"],
        fetch_text=lambda url: RSS_SAMPLE if url.endswith("rss.xml") else ARTICLE_HTML_SAMPLE,
    )
    assert rss_items[0]["title"] == "OpenAI launches new enterprise API tier"
    assert rss_items[0]["url"] == "https://openai.com/news/enterprise-api-tier"
    assert "stronger compliance controls" in rss_items[0]["content_excerpt"]

    atom_items = fetch_source_items(
        by_id["geeknews"],
        fetch_text=lambda url: ATOM_SAMPLE if "feed" in url else ARTICLE_HTML_SAMPLE,
    )
    assert atom_items[0]["title"] == "OpenAI launches new enterprise API tier"
    assert atom_items[0]["external_id"] == "tag:hada.io,2026:123"
    assert "frontier models in production" in atom_items[0]["content_excerpt"]

    html_sample = """
    <html><body>
      <a href='/news/claude-opus-4-7'>Introducing Claude Opus 4.7</a>
      <a href='/about'>About</a>
    </body></html>
    """
    html_items = fetch_source_items(
        by_id["anthropic-news"],
        fetch_text=lambda url: html_sample if url == "https://www.anthropic.com/news" else ARTICLE_HTML_SAMPLE,
    )
    assert html_items[0]["title"] == "Introducing Claude Opus 4.7"
    assert html_items[0]["url"] == "https://www.anthropic.com/news/claude-opus-4-7"
    assert "predictable procurement" in html_items[0]["content_excerpt"]

    x_items = fetch_source_items(
        by_id["openai-x"],
        fetch_text=lambda url: NITTER_RSS_SAMPLE if url.endswith("/rss") else X_STATUS_HTML_SAMPLE,
    )
    assert x_items[0]["external_id"] == "1912345678901234567"
    assert x_items[0]["url"] == "https://x.com/OpenAI/status/1912345678901234567"
    assert x_items[0]["author"] == "OpenAI"
    assert x_items[0]["engagement"]["reply_count"] == 42
    assert x_items[0]["engagement"]["favorite_count"] == 1500
    assert x_items[0]["engagement"]["score"] == 1826
    assert x_items[0]["engagement"]["comments"] == 42

    def fake_fetch_json(url: str):
        if url.endswith("topstories.json"):
            return [101]
        if url.endswith("/item/101.json"):
            return {
                "id": 101,
                "title": "Show HN: OpenAI launches new enterprise API tier",
                "url": "https://openai.com/news/enterprise-api-tier",
                "by": "alice",
                "score": 77,
                "descendants": 15,
                "time": 1770000000,
            }
        raise AssertionError(url)

    api_items = fetch_source_items(
        by_id["hackernews-topstories"],
        fetch_json=fake_fetch_json,
        fetch_text=lambda url: ARTICLE_HTML_SAMPLE if "enterprise-api-tier" in url else "",
    )
    assert api_items[0]["title"].startswith("Show HN")
    assert api_items[0]["engagement"]["score"] == 77
    assert "stronger compliance controls" in api_items[0]["content_excerpt"]



def test_content_enrichment_searches_by_title_when_original_page_has_no_readable_text(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    _write_sources(tmp_path)
    source = {source.source_id: source for source in load_watch_sources(config)}["hackernews-topstories"]

    def fake_fetch_json(url: str):
        if url.endswith("topstories.json"):
            return [101]
        if url.endswith("/item/101.json"):
            return {
                "id": 101,
                "title": "Show HN: OpenAI launches new enterprise API tier",
                "url": "https://blocked.example.com/original",
                "by": "alice",
                "score": 77,
                "descendants": 15,
                "time": 1770000000,
            }
        raise AssertionError(url)

    fetched_urls: list[str] = []

    def fake_fetch_text(url: str) -> str:
        fetched_urls.append(url)
        if url == "https://blocked.example.com/original":
            return "<html><body><script>blocked</script></body></html>"
        if url.startswith("https://duckduckgo.com/html/"):
            return SEARCH_HTML_SAMPLE
        if url == "https://mirror.example.com/openai-enterprise-api-tier":
            return MIRROR_ARTICLE_HTML_SAMPLE
        raise AssertionError(url)

    items = fetch_source_items(source, fetch_json=fake_fetch_json, fetch_text=fake_fetch_text)

    assert "audit controls" in items[0]["content_excerpt"]
    assert items[0]["content_source_url"] == "https://mirror.example.com/openai-enterprise-api-tier"
    assert any(url.startswith("https://duckduckgo.com/html/") and "openai" in url for url in fetched_urls)



def test_x_source_searches_by_title_when_status_page_has_no_readable_content(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    _write_sources(tmp_path)
    source = {source.source_id: source for source in load_watch_sources(config)}["openai-x"]

    def fake_fetch_text(url: str) -> str:
        if url.endswith("/rss"):
            return NITTER_RSS_SAMPLE
        if url == "https://x.com/OpenAI/status/1912345678901234567":
            return X_STATUS_HTML_SAMPLE
        if url.startswith("https://duckduckgo.com/html/"):
            return SEARCH_HTML_SAMPLE
        if url == "https://mirror.example.com/openai-enterprise-api-tier":
            return MIRROR_ARTICLE_HTML_SAMPLE
        raise AssertionError(url)

    items = fetch_source_items(source, fetch_text=fake_fetch_text)

    assert "audit controls" in items[0]["content_excerpt"]
    assert items[0]["content_source_url"] == "https://mirror.example.com/openai-enterprise-api-tier"
    assert items[0]["engagement"]["score"] == 1826



def test_json_feed_sources_are_parsed_and_enriched_with_article_content(tmp_path: Path):
    source = WatchSource(
        source_id="cisco-cloud-news",
        display_name="Cisco Newsroom Cloud Feed",
        company_tag="cisco",
        source_class="company",
        source_role="official-origin",
        source_type="rss",
        ingest_strategy="rss",
        base_url="https://newsroom.cisco.com/",
        feed_url="https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json?feed=cloud",
        html_list_url="https://newsroom.cisco.com/c/r/newsroom/en/us/rss-feeds.html",
        poll_minutes=60,
        enabled=True,
        validation_status="verified",
        validation_notes=("json-feed",),
        browser_required=False,
        anti_bot_risk="low",
        priority_weight=0.75,
        reaction_weight=0.0,
        cooldown_minutes=60,
        topic_tags=("cloud",),
        file_path=tmp_path / "cisco-cloud.yaml",
    )

    items = fetch_source_items(
        source,
        fetch_text=lambda url: JSON_FEED_SAMPLE if url.endswith("rssfeed.json?feed=cloud") else ARTICLE_HTML_SAMPLE,
    )

    assert items[0]["title"] == "Cisco expands cloud networking security"
    assert items[0]["url"] == "https://newsroom.cisco.com/news/cloud-security"
    assert "cloud networking security updates" in items[0]["summary_text"]
    assert "large organizations" in items[0]["content_excerpt"]



def test_extract_x_status_id_and_parse_metrics_helpers():
    assert extract_x_status_id("https://nitter.net/OpenAI/status/1912345678901234567#m") == "1912345678901234567"
    assert extract_x_status_id("https://x.com/OpenAI/status/1912345678901234567") == "1912345678901234567"
    assert extract_x_status_id("1912345678901234567") == "1912345678901234567"
    assert parse_x_status_metrics(X_STATUS_HTML_SAMPLE) == {
        "reply_count": 42,
        "retweet_count": 314,
        "quote_count": 12,
        "favorite_count": 1500,
    }



def test_watch_pipeline_loads_sources_dedups_reactions_and_generates_report(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    _write_sources(tmp_path)
    bootstrap_workspace(config)

    sources = load_watch_sources(config)
    assert [s.source_id for s in sources] == ["anthropic-news", "openai-news", "openai-x", "geeknews", "hackernews-topstories"]

    sync_result = sync_watch_sources(config)
    assert sync_result["source_count"] == 5

    def fake_fetcher(source):
        if source.source_id == "anthropic-news":
            return [{
                "title": "Introducing Claude Opus 4.7",
                "url": "https://www.anthropic.com/news/claude-opus-4-7",
                "summary_text": "official launch",
                "published_at": _recent_iso(minutes_ago=20),
            }]
        if source.source_id == "openai-news":
            return [{
                "title": "OpenAI launches new enterprise API tier",
                "url": "https://openai.com/news/enterprise-api-tier",
                "summary_text": "official launch",
                "published_at": _recent_iso(minutes_ago=15),
            }]
        if source.source_id == "openai-x":
            return [{
                "title": "OpenAI launches new enterprise API tier",
                "url": "https://x.com/OpenAI/status/1912345678901234567",
                "external_id": "1912345678901234567",
                "author": "OpenAI",
                "summary_text": "official x thread",
                "published_at": _recent_iso(minutes_ago=10),
                "engagement": {
                    "reply_count": 42,
                    "retweet_count": 314,
                    "quote_count": 12,
                    "favorite_count": 1500,
                    "score": 1826,
                    "comments": 42,
                },
            }]
        if source.source_id == "geeknews":
            return [{
                "title": "OpenAI launches new enterprise API tier",
                "url": "https://news.hada.io/topic?id=123",
                "summary_text": "community reaction",
                "published_at": _recent_iso(minutes_ago=8),
            }]
        return [{
            "title": "Show HN: OpenAI launches new enterprise API tier",
            "url": "https://news.ycombinator.com/item?id=101",
            "summary_text": "hn reaction",
            "published_at": _recent_iso(minutes_ago=5),
            "engagement": {"score": 77, "comments": 15},
        }]

    collect_result = collect_watch_signals(config, fetcher=fake_fetcher)
    assert collect_result["signal_count"] == 5

    with sqlite3.connect(config.database_path) as conn:
        row = conn.execute(
            "SELECT url, external_id, engagement_json FROM watch_signals WHERE source_id = ?",
            ("openai-x",),
        ).fetchone()
    assert row[0] == "https://x.com/OpenAI/status/1912345678901234567"
    assert row[1] == "1912345678901234567"
    assert json.loads(row[2])["favorite_count"] == 1500

    build_result = build_watch_stories(config)
    assert build_result["issue_count"] == 2

    judge_result = judge_watch_issues(config)
    assert judge_result["judged_count"] == 2

    report_result = generate_watch_report(config)
    assert report_result["artifact_path"].exists()
    text = report_result["artifact_path"].read_text(encoding="utf-8")
    assert "## 🔥 핫이슈 업데이트" in text
    assert "**신규 이슈:**" in text
    assert "### 1. OpenAI launches new enterprise API tier" in text
    assert "**관심도:** 중요도" in text
    assert "**내용 요약:**" in text
    assert "**왜 중요한가:**" in text
    assert "**정량 신호:**" in text
    assert "**출처:**" in text
    assert "외부 핫이슈" not in text
    assert "- importance:" not in text
    assert "- origin:" not in text
    assert "OpenAI launches new enterprise API tier" in text
    assert report_result["issue_count"] >= 1


def test_generate_watch_report_suppresses_low_importance_momentum_only_false_positive(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    false_judgment = {
        "is_true_hot_issue": False,
        "importance_score_adjusted": 0.155,
        "momentum_score_adjusted": 0.181,
        "heat_level": "low",
        "judgment_reason": "heuristic fallback for low-importance HN link",
        "should_alert_now": False,
    }
    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            """
            INSERT INTO watch_signals (
                signal_id, source_id, source_type, signal_kind, title, url,
                summary_text, published_at, collected_at, engagement_json,
                topic_tags_json, entity_tags_json, canonical_key, content_hash, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sig-low",
                "hackernews-topstories",
                "hackernews",
                "community-thread",
                "Amateur armed with ChatGPT solves an Erdős problem",
                "https://www.scientificamerican.com/article/amateur-armed-with-chatgpt-vibe-maths-a-60-year-old-problem/",
                "single community link",
                now,
                now,
                json.dumps({"score": 114, "comments": 61}),
                "[]",
                "[]",
                "low-key",
                "hash-low",
                json.dumps({"content_excerpt": "math curiosity, not AI/cloud infrastructure news"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO watch_issue_stories (
                issue_id, story_key, canonical_title, canonical_summary, primary_company_tag,
                topic_ids_json, entity_tags_json, origin_signal_id, origin_kind,
                first_seen_at, last_seen_at, current_importance_score, current_momentum_score,
                current_heat_level, report_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "issue-low",
                "story-low",
                "Amateur armed with ChatGPT solves an Erdős problem",
                "single community link",
                None,
                "[]",
                "[]",
                "sig-low",
                "community-thread",
                now,
                now,
                0.155,
                0.181,
                "low",
                "unseen",
            ),
        )
        conn.execute(
            """
            INSERT INTO watch_issue_snapshots (
                snapshot_id, issue_id, snapshot_hour, signal_count, official_signal_count,
                community_signal_count, unique_source_count, engagement_score, reaction_score,
                importance_score, momentum_score, heat_level, llm_judgment_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("snap-low", "issue-low", now, 1, 0, 1, 1, 114.0, 61.0, 0.155, 0.181, "low", json.dumps(false_judgment)),
        )
        conn.commit()

    report_result = generate_watch_report(config)

    assert report_result["message_text"] == "[SILENT]"
    assert report_result["issue_count"] == 0


def test_generate_watch_report_uses_news_center_when_hot_issue_threshold_is_quiet(tmp_path: Path, monkeypatch):
    config_path = _write_config(tmp_path)
    taxonomy = tmp_path / "config/personal-radar/naver-news-taxonomy.yaml"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.write_text("categories: []\n", encoding="utf-8")
    config = load_pipeline_config(config_path)
    bootstrap_workspace(config)

    def fake_collect_news_center(**kwargs):
        assert kwargs["taxonomy_path"] == taxonomy
        assert kwargs["per_source_limit"] == 1
        return {
            "artifact_path": str(tmp_path / "data/news-center/news-center.json"),
            "markdown_path": str(tmp_path / "data/news-center/news-center.md"),
            "item_count": 2,
            "error_count": 0,
            "news_markdown": "## 뉴스 센터 브리핑\n\n### 기술 · 국내\n\n- 확인된 사실: AI 반도체 정책 발표\n- 왜 중요한가: 국내 기술 흐름 확인\n- 오늘 할 일: 원문 확인\n- 근거: google-news / 2026-04-26\n- 불확실성: 자동 수집 요약",
        }

    monkeypatch.setattr("jinwang_jarvis.watch.collect_news_center", fake_collect_news_center)

    report_result = generate_watch_report(config)

    assert report_result["issue_count"] == 1
    assert "## 📰 뉴스 센터 업데이트" in report_result["message_text"]
    assert "고임계값 핫이슈는 없지만" in report_result["message_text"]
    assert "AI 반도체 정책 발표" in report_result["message_text"]
    assert str(tmp_path) not in report_result["message_text"]
    assert report_result["artifact_path"].read_text(encoding="utf-8") == report_result["message_text"]


def test_generate_external_hot_issue_alert_advances_new_window_and_dedupes_repeats(tmp_path: Path):
    state_path = tmp_path / "state/external_hot_issue_state.json"
    report_path = tmp_path / "data/watch/reports/hourly-hot-issues-20260424T100234+0000.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        """## 🔥 핫이슈 업데이트

**생성 시각:** 2026-04-24T10:02:34+00:00
**신규 이슈:** 2건

### 1. GPT-5.5
**분류:** unknown · **열기:** low
**관심도:** 중요도 **0.642** · 모멘텀 **0.401**
**관측 신호:** 총 2 · 공식 0 · 커뮤니티 2 · 출처 2
**반응:** 참여 1374.0 · 리액션 904.0
**내용 요약:** OpenAI가 신규 모델/API를 공개했고 엔터프라이즈 사용자를 위한 배포 옵션을 설명했습니다.
**왜 중요한가:** OpenAI의 신규 모델/API 공개로 개발자 생태계와 클라우드 사용량에 직접 영향이 있습니다.
**출처:** https://openai.com/index/introducing-gpt-5-5/

### 2. Meta tells staff it will cut 10% of jobs
**분류:** meta · **열기:** low
**관심도:** 중요도 **0.364** · 모멘텀 **0.175**
**관측 신호:** 총 1 · 공식 0 · 커뮤니티 1 · 출처 1
**반응:** 참여 584.0 · 리액션 559.0
**왜 이슈인가:** Meta 조직 축소는 AI 투자 우선순위와 비용 구조 변화의 신호입니다.
**출처:** https://www.bloomberg.com/news/articles/2026-04-23/meta-tells-staff-it-will-cut-10-of-jobs-in-push-for-efficiency
""",
        encoding="utf-8",
    )
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "window_end_day_kst": "2026-04-24",
                "seen_issue_keys": ["https://old.example/issue"],
                "day_issue_records": [{"key": "https://old.example/issue", "title": "old"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    first = generate_external_hot_issue_alert(
        report_path=report_path,
        state_path=state_path,
        now=datetime(2026, 4, 24, 19, 3, tzinfo=UTC).astimezone().replace(tzinfo=UTC),
    )
    second = generate_external_hot_issue_alert(
        report_path=report_path,
        state_path=state_path,
        now=datetime(2026, 4, 24, 19, 33, tzinfo=UTC).astimezone().replace(tzinfo=UTC),
    )

    assert first["window_end_day_kst"] == "2026-04-25"
    assert first["new_count"] == 2
    assert "## 🔥 핫이슈 업데이트" in first["message_text"]
    assert "**신규 이슈:** 2건" in first["message_text"]
    assert "### 1. GPT-5.5" in first["message_text"]
    assert "**관심도:** 중요도 **0.642** · 모멘텀 **0.401**" in first["message_text"]
    assert "**내용 요약:** OpenAI가 신규 모델/API를 공개했고 엔터프라이즈 사용자를 위한 배포 옵션을 설명했습니다." in first["message_text"]
    assert "**왜 중요한가:** OpenAI의 신규 모델/API 공개로 개발자 생태계와 클라우드 사용량에 직접 영향이 있습니다." in first["message_text"]
    assert "**출처:** https://openai.com/index/introducing-gpt-5-5/" in first["message_text"]
    assert "외부 핫이슈" not in first["message_text"]
    assert "GPT-5.5" in first["message_text"]
    assert second["new_count"] == 0
    assert second["message_text"] == "[SILENT]"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["window_end_day_kst"] == "2026-04-25"
    assert "https://openai.com/index/introducing-gpt-5-5" in state["seen_issue_keys"]
    assert "https://old.example/issue" not in state["seen_issue_keys"]


def test_generate_external_hot_issue_alert_does_not_roll_back_newer_window_state(tmp_path: Path):
    state_path = tmp_path / "state/external_hot_issue_state.json"
    report_path = tmp_path / "report.md"
    report_path.write_text(
        """# hourly-hot-issues
generated_at: 2026-04-24T10:33:16+00:00

## 1. GPT-5.5
- company: unknown | heat: low
- importance: 0.642 | momentum: 0.401
- signals: total=2, official=0, community=2, sources=2
- engagement: 1374.0 | reaction: 904.0
- origin: https://openai.com/index/introducing-gpt-5-5/
""",
        encoding="utf-8",
    )
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "window_end_day_kst": "2026-04-25",
                "seen_issue_keys": ["https://openai.com/index/introducing-gpt-5-5"],
                "day_issue_records": [
                    {"key": "https://openai.com/index/introducing-gpt-5-5", "title": "GPT-5.5"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = generate_external_hot_issue_alert(
        report_path=report_path,
        state_path=state_path,
        now=datetime(2026, 4, 24, 19, 34, tzinfo=UTC).astimezone().replace(tzinfo=UTC),
    )

    assert result["message_text"] == "[SILENT]"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["window_end_day_kst"] == "2026-04-25"
    assert state["seen_issue_keys"] == ["https://openai.com/index/introducing-gpt-5-5"]
