from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import PipelineConfig

REQUIRED_DIRECTORIES = [
    Path("data/snapshots/mail"),
    Path("data/snapshots/calendar"),
    Path("data/intelligence"),
    Path("data/exports"),
    Path("data/proposals"),
    Path("data/digests"),
    Path("data/briefings"),
    Path("data/feedback"),
    Path("data/watchlists"),
    Path("state"),
    Path("state/locks"),
]

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS messages (
        message_id TEXT PRIMARY KEY,
        account TEXT NOT NULL,
        folder_kind TEXT NOT NULL,
        thread_key TEXT,
        subject TEXT,
        from_addr TEXT,
        to_addrs TEXT,
        cc_addrs TEXT,
        self_role TEXT,
        interaction_role TEXT,
        sent_at TEXT,
        snippet TEXT,
        body_path TEXT,
        raw_json_path TEXT,
        is_seen INTEGER DEFAULT 0,
        ingested_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sender_identities (
        email TEXT PRIMARY KEY,
        display_name TEXT,
        role TEXT NOT NULL,
        organization TEXT,
        priority_base INTEGER DEFAULT 0,
        source_note TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS message_labels (
        message_id TEXT NOT NULL,
        label TEXT NOT NULL,
        score REAL NOT NULL,
        reason_json TEXT,
        PRIMARY KEY (message_id, label)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_message_id TEXT,
        signal_type TEXT NOT NULL,
        evidence_message_id TEXT,
        score REAL NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_proposals (
        proposal_id TEXT PRIMARY KEY,
        source_message_id TEXT,
        title TEXT NOT NULL,
        start_ts TEXT,
        end_ts TEXT,
        location TEXT,
        description_md TEXT,
        confidence REAL NOT NULL,
        status TEXT NOT NULL,
        dedup_key TEXT,
        reason_json TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calendar_events (
        event_id TEXT PRIMARY KEY,
        calendar_id TEXT NOT NULL,
        summary TEXT,
        status TEXT,
        start_ts TEXT,
        end_ts TEXT,
        location TEXT,
        html_link TEXT,
        dedup_key TEXT NOT NULL,
        raw_json_path TEXT,
        ingested_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS proposal_feedback (
        proposal_id TEXT PRIMARY KEY,
        decision TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        freeform_note TEXT,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backfill_runs (
        window_name TEXT PRIMARY KEY,
        window_start TEXT,
        window_end TEXT,
        status TEXT NOT NULL,
        messages_scanned INTEGER DEFAULT 0,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS message_watchlist (
        source_message_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        watch_kind TEXT NOT NULL,
        promotion_score REAL NOT NULL,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        seen_count INTEGER NOT NULL DEFAULT 1,
        latest_reason_json TEXT,
        latest_artifact_file TEXT,
        wiki_note_path TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS message_participant_cache (
        message_id TEXT PRIMARY KEY,
        account TEXT,
        folder_name TEXT,
        source_id TEXT,
        to_addrs_json TEXT,
        cc_addrs_json TEXT,
        reply_to_addrs_json TEXT,
        delivered_to TEXT,
        references_json TEXT,
        message_id_header TEXT,
        in_reply_to TEXT,
        header_hash TEXT,
        cached_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_messages (
        knowledge_id TEXT PRIMARY KEY,
        account TEXT NOT NULL,
        folder_name TEXT NOT NULL,
        source_id TEXT NOT NULL,
        subject TEXT,
        from_addr TEXT,
        to_addr TEXT,
        to_addrs_json TEXT,
        cc_addrs_json TEXT,
        self_role TEXT,
        interaction_role TEXT,
        sent_at TEXT,
        has_attachment INTEGER DEFAULT 0,
        category TEXT NOT NULL,
        tags_json TEXT,
        importance_score REAL NOT NULL,
        opportunity_score REAL NOT NULL,
        summary_text TEXT,
        collected_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_intelligence_reports (
        report_id TEXT PRIMARY KEY,
        generated_at TEXT NOT NULL,
        lookback_days INTEGER NOT NULL,
        item_count INTEGER NOT NULL,
        opportunity_count INTEGER NOT NULL,
        artifact_file TEXT NOT NULL,
        wiki_note_path TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watch_sources (
        source_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        company_tag TEXT,
        source_class TEXT,
        source_role TEXT NOT NULL,
        source_type TEXT NOT NULL,
        ingest_strategy TEXT NOT NULL,
        base_url TEXT NOT NULL,
        feed_url TEXT,
        html_list_url TEXT,
        poll_minutes INTEGER NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        validation_status TEXT,
        validation_notes_json TEXT,
        browser_required INTEGER NOT NULL DEFAULT 0,
        anti_bot_risk TEXT,
        priority_weight REAL NOT NULL DEFAULT 0,
        reaction_weight REAL NOT NULL DEFAULT 0,
        cooldown_minutes INTEGER NOT NULL DEFAULT 60,
        topic_tags_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watch_signals (
        signal_id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        source_type TEXT NOT NULL,
        signal_kind TEXT NOT NULL,
        company_tag TEXT,
        external_id TEXT,
        title TEXT,
        url TEXT,
        author TEXT,
        summary_text TEXT,
        published_at TEXT,
        collected_at TEXT NOT NULL,
        engagement_json TEXT,
        topic_tags_json TEXT,
        entity_tags_json TEXT,
        language TEXT,
        canonical_key TEXT,
        content_hash TEXT,
        raw_payload_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watch_issue_stories (
        issue_id TEXT PRIMARY KEY,
        story_key TEXT UNIQUE,
        canonical_title TEXT,
        canonical_summary TEXT,
        primary_company_tag TEXT,
        topic_ids_json TEXT,
        entity_tags_json TEXT,
        origin_signal_id TEXT,
        origin_kind TEXT,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        current_importance_score REAL NOT NULL DEFAULT 0,
        current_momentum_score REAL NOT NULL DEFAULT 0,
        current_heat_level TEXT NOT NULL DEFAULT 'low',
        report_status TEXT NOT NULL DEFAULT 'unseen',
        last_reported_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watch_issue_signals (
        issue_id TEXT NOT NULL,
        signal_id TEXT NOT NULL,
        role TEXT NOT NULL,
        PRIMARY KEY (issue_id, signal_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watch_issue_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        issue_id TEXT NOT NULL,
        snapshot_hour TEXT NOT NULL,
        signal_count INTEGER NOT NULL,
        official_signal_count INTEGER NOT NULL,
        community_signal_count INTEGER NOT NULL,
        unique_source_count INTEGER NOT NULL,
        engagement_score REAL NOT NULL,
        reaction_score REAL NOT NULL,
        importance_score REAL NOT NULL,
        momentum_score REAL NOT NULL,
        heat_level TEXT NOT NULL,
        llm_judgment_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watch_reports (
        report_id TEXT PRIMARY KEY,
        generated_at TEXT NOT NULL,
        report_kind TEXT NOT NULL,
        issue_ids_json TEXT NOT NULL,
        artifact_file TEXT NOT NULL,
        delivered_channel TEXT
    )
    """,
]


def bootstrap_workspace(config: PipelineConfig) -> None:
    for relative_dir in REQUIRED_DIRECTORIES:
        (config.workspace_root / relative_dir).mkdir(parents=True, exist_ok=True)
    config.watch.snapshot_dir.mkdir(parents=True, exist_ok=True)
    (config.watch.snapshot_dir / 'reports').mkdir(parents=True, exist_ok=True)
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.database_path) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        existing_message_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        for col, spec in {
            "self_role": "TEXT",
            "interaction_role": "TEXT",
        }.items():
            if col not in existing_message_cols:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {spec}")
        existing_cache_cols = {row[1] for row in conn.execute("PRAGMA table_info(message_participant_cache)").fetchall()}
        for col, spec in {
            "message_id_header": "TEXT",
            "in_reply_to": "TEXT",
        }.items():
            if col not in existing_cache_cols:
                conn.execute(f"ALTER TABLE message_participant_cache ADD COLUMN {col} {spec}")
        existing_knowledge_cols = {row[1] for row in conn.execute("PRAGMA table_info(knowledge_messages)").fetchall()}
        for col, spec in {
            "to_addrs_json": "TEXT",
            "cc_addrs_json": "TEXT",
            "self_role": "TEXT",
            "interaction_role": "TEXT",
        }.items():
            if col not in existing_knowledge_cols:
                conn.execute(f"ALTER TABLE knowledge_messages ADD COLUMN {col} {spec}")
        conn.commit()
