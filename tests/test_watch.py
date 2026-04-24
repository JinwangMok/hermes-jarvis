import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jinwang_jarvis.bootstrap import bootstrap_workspace
from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.watch import (
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

    rss_items = fetch_source_items(by_id["openai-news"], fetch_text=lambda _url: RSS_SAMPLE)
    assert rss_items[0]["title"] == "OpenAI launches new enterprise API tier"
    assert rss_items[0]["url"] == "https://openai.com/news/enterprise-api-tier"

    atom_items = fetch_source_items(by_id["geeknews"], fetch_text=lambda _url: ATOM_SAMPLE)
    assert atom_items[0]["title"] == "OpenAI launches new enterprise API tier"
    assert atom_items[0]["external_id"] == "tag:hada.io,2026:123"

    html_sample = """
    <html><body>
      <a href='/news/claude-opus-4-7'>Introducing Claude Opus 4.7</a>
      <a href='/about'>About</a>
    </body></html>
    """
    html_items = fetch_source_items(by_id["anthropic-news"], fetch_text=lambda _url: html_sample)
    assert html_items[0]["title"] == "Introducing Claude Opus 4.7"
    assert html_items[0]["url"] == "https://www.anthropic.com/news/claude-opus-4-7"

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
                "url": "https://news.ycombinator.com/item?id=101",
                "by": "alice",
                "score": 77,
                "descendants": 15,
                "time": 1770000000,
            }
        raise AssertionError(url)

    api_items = fetch_source_items(by_id["hackernews-topstories"], fetch_json=fake_fetch_json)
    assert api_items[0]["title"].startswith("Show HN")
    assert api_items[0]["engagement"]["score"] == 77



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
    assert "OpenAI launches new enterprise API tier" in text
    assert report_result["issue_count"] >= 1


def test_generate_external_hot_issue_alert_advances_new_window_and_dedupes_repeats(tmp_path: Path):
    state_path = tmp_path / "state/external_hot_issue_state.json"
    report_path = tmp_path / "data/watch/reports/hourly-hot-issues-20260424T100234+0000.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        """# hourly-hot-issues
generated_at: 2026-04-24T10:02:34+00:00

## 1. GPT-5.5
- company: unknown | heat: low
- importance: 0.642 | momentum: 0.401
- signals: total=2, official=0, community=2, sources=2
- engagement: 1374.0 | reaction: 904.0
- origin: https://openai.com/index/introducing-gpt-5-5/

## 2. Meta tells staff it will cut 10% of jobs
- company: meta | heat: low
- importance: 0.364 | momentum: 0.175
- signals: total=1, official=0, community=1, sources=1
- engagement: 584.0 | reaction: 559.0
- origin: https://www.bloomberg.com/news/articles/2026-04-23/meta-tells-staff-it-will-cut-10-of-jobs-in-push-for-efficiency
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
