from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "config" / "watch-sources"


def _load_sources():
    sources = {}
    for path in SOURCE_ROOT.rglob("*.yaml"):
        if path.name == "MANIFEST.yaml":
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sources[raw["source_id"]] = raw
    return sources


def test_watch_sources_include_major_ai_research_conference_lane():
    sources = _load_sources()
    required_feeds = {
        "neurips-blog": "https://blog.neurips.cc/feed/",
        "aaai-news": "https://aaai.org/feed/",
        "arxiv-cs-ai": "https://arxiv.org/rss/cs.AI",
        "arxiv-cs-lg": "https://arxiv.org/rss/cs.LG",
    }
    for source_id, feed_url in required_feeds.items():
        source = sources[source_id]
        assert source["enabled"] is True
        assert source["feed_url"] == feed_url
        assert source["source_role"] in {"official-origin", "research-signal"}
        assert "research" in source["topic_tags"]

    required_html = {
        "icml-conference": "https://icml.cc/Conferences/2026",
        "iclr-conference": "https://iclr.cc/Conferences/2026",
    }
    for source_id, html_url in required_html.items():
        source = sources[source_id]
        assert source["enabled"] is True
        assert source["ingest_strategy"] == "html"
        assert source["html_list_url"] == html_url
        assert "research" in source["topic_tags"]


def test_watch_sources_include_cloud_native_activity_lane():
    sources = _load_sources()
    required = {
        "cncf-blog",
        "kubernetes-blog",
        "kubecon-cloudnativecon-europe",
        "kubernetes-contributors-blog",
    }
    assert required <= set(sources)
    for source_id in required:
        source = sources[source_id]
        assert source["enabled"] is True
        assert any(tag in source["topic_tags"] for tag in ["kubernetes", "cloud-native", "cncf"])
        assert source["priority_weight"] >= 0.65


def test_watch_sources_include_realtime_x_and_korean_government_content_lanes():
    sources = _load_sources()
    x_source = sources["x-realtime-ai-research-search"]
    assert x_source["ingest_strategy"] == "x-search"
    assert x_source["enabled"] is False
    assert "xurl" in " ".join(x_source["validation_notes"]).lower()
    assert "--bearer-token" not in " ".join(x_source["validation_notes"])

    required_government = {"msit-home", "iitp-notices", "nrf-notices"}
    assert required_government <= set(sources)
    for source_id in required_government:
        source = sources[source_id]
        assert source["enabled"] is True
        assert source["source_class"] == "government"
        assert source["ingest_strategy"] == "html"
        assert source["priority_weight"] >= 0.85
        assert any(tag in source["topic_tags"] for tag in ["ai", "rnd", "research", "ict"])
