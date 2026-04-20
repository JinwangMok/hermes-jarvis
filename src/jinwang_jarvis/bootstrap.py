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
]


def bootstrap_workspace(config: PipelineConfig) -> None:
    for relative_dir in REQUIRED_DIRECTORIES:
        (config.workspace_root / relative_dir).mkdir(parents=True, exist_ok=True)

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
