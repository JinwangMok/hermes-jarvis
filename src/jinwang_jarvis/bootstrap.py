from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import PipelineConfig

REQUIRED_DIRECTORIES = [
    Path("data/snapshots/mail"),
    Path("data/snapshots/calendar"),
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
]


def bootstrap_workspace(config: PipelineConfig) -> None:
    for relative_dir in REQUIRED_DIRECTORIES:
        (config.workspace_root / relative_dir).mkdir(parents=True, exist_ok=True)

    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.database_path) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.commit()
