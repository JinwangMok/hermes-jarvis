import sqlite3
from pathlib import Path

import pytest

from jinwang_jarvis.bootstrap import bootstrap_workspace, ensure_search_indexes
from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.wiki_search import rebuild_operational_search_index, search_operational_index


def _config_text(root: Path) -> str:
    return """
workspace_root: {root}
wiki_root: {wiki}
accounts:
  - personal
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
  deliver_channel: discord-origin
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: jinwang-jarvis
watch:
  enabled: true
  snapshot_dir: data/watch
  source_config_dir: config/watch-sources
""".format(root=root.as_posix(), wiki=(root / "wiki").as_posix())


def _load_config(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")
    return load_pipeline_config(config_file)


def _fts5_available(conn: sqlite3.Connection) -> bool:
    return bool(ensure_search_indexes(conn).get("fts5_available"))


def test_ensure_search_indexes_is_idempotent(tmp_path: Path):
    with sqlite3.connect(tmp_path / "test.db") as conn:
        first = ensure_search_indexes(conn)
        second = ensure_search_indexes(conn)
        if not first.get("fts5_available"):
            assert first["reason"] == "fts5_unavailable"
            return
        assert second["fts5_available"] is True
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"messages_fts", "knowledge_messages_fts", "watch_signals_fts", "watch_issue_stories_fts"} <= tables


def test_rebuild_and_search_operational_index_normalizes_sources(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        if not _fts5_available(conn):
            pytest.skip("SQLite build lacks FTS5")
        conn.execute("INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, snippet, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("m1", "personal", "inbox", "Jongwon meeting", "jongwon@example.com", "2026-04-30T00:00:00Z", "Discuss search", "2026-04-30T00:00:00Z"))
        conn.execute("INSERT INTO knowledge_messages (knowledge_id, account, folder_name, source_id, subject, from_addr, sent_at, category, importance_score, opportunity_score, summary_text, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("k1", "personal", "all", "src1", "연구 Jongwon", "lab@example.com", "2026-04-29T00:00:00Z", "research", 1.0, 0.0, "한국어 검색", "2026-04-30T00:00:00Z"))
        conn.execute("INSERT INTO watch_signals (signal_id, source_id, source_type, signal_kind, title, author, summary_text, url, published_at, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("s1", "src", "rss", "post", "Jongwon release", "author", "signal summary", "https://example.com/item", "2026-04-28T00:00:00Z", "2026-04-30T00:00:00Z"))
        conn.execute("INSERT INTO watch_issue_stories (issue_id, story_key, canonical_title, canonical_summary, primary_company_tag, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?)", ("i1", "story", "Jongwon story", "issue summary", "lab", "2026-04-27T00:00:00Z", "2026-04-30T00:00:00Z"))
        conn.commit()

    first = rebuild_operational_search_index(config.database_path)
    second = rebuild_operational_search_index(config.database_path)
    assert first["ok"] is True
    assert second["indexed_rows"] == first["indexed_rows"]

    result = search_operational_index(config.database_path, "Jongwon", limit=10)
    assert result["ok"] is True
    rows = result["rows"]
    assert {(row["source_table"], row["source_id"]) for row in rows} == {
        ("messages", "m1"),
        ("knowledge_messages", "k1"),
        ("watch_signals", "s1"),
        ("watch_issue_stories", "i1"),
    }

    korean_result = search_operational_index(config.database_path, "한국어", limit=10)
    assert korean_result["ok"] is True
    assert {(row["source_table"], row["source_id"]) for row in korean_result["rows"]} == {("knowledge_messages", "k1")}


def test_search_operational_index_handles_invalid_query(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        if not _fts5_available(conn):
            pytest.skip("SQLite build lacks FTS5")
    result = search_operational_index(config.database_path, '"unterminated', limit=5)
    assert result["ok"] is False
    assert result["reason"] == "invalid_query"
