"""Canonical SQLite schema for Zeus OS."""

from __future__ import annotations

SCHEMA_VERSION = 1

MIGRATIONS = [
    # Migration 0 -> 1: initial schema
    [
        # Migrations tracking
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS runtime_metadata (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Agent registry
        """
        CREATE TABLE IF NOT EXISTS agent_cards (
            agent_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            persona_type TEXT NOT NULL,
            description TEXT,
            version TEXT NOT NULL DEFAULT '0.1.0',
            capabilities_json TEXT NOT NULL DEFAULT '[]',
            skills_json TEXT NOT NULL DEFAULT '[]',
            protocols_json TEXT NOT NULL DEFAULT '[]',
            registry_metadata_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Workers
        """
        CREATE TABLE IF NOT EXISTS worker_agents (
            worker_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL REFERENCES agent_cards(agent_id),
            kind TEXT NOT NULL,
            display_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'idle',
            capabilities_json TEXT NOT NULL DEFAULT '[]',
            current_work_order_id TEXT,
            heartbeat_at TEXT,
            lease_owner TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Contexts
        """
        CREATE TABLE IF NOT EXISTS contexts (
            context_id TEXT PRIMARY KEY,
            origin_platform TEXT NOT NULL DEFAULT 'cli',
            origin_channel_id TEXT,
            origin_thread_id TEXT,
            origin_message_id TEXT,
            user_id TEXT,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Boardroom sessions
        """
        CREATE TABLE IF NOT EXISTS boardroom_sessions (
            session_id TEXT PRIMARY KEY,
            context_id TEXT REFERENCES contexts(context_id),
            task_id TEXT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            max_rounds INTEGER NOT NULL DEFAULT 5,
            current_round INTEGER NOT NULL DEFAULT 0,
            final_arbiter_agent_id TEXT,
            budget_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS boardroom_participants (
            session_id TEXT NOT NULL REFERENCES boardroom_sessions(session_id) ON DELETE CASCADE,
            agent_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'participant',
            status TEXT NOT NULL DEFAULT 'active',
            turn_budget_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            joined_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (session_id, agent_id)
        )
        """,
        # Messages
        """
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            context_id TEXT REFERENCES contexts(context_id),
            task_id TEXT,
            role TEXT NOT NULL,
            sender_agent_id TEXT,
            parts_json TEXT NOT NULL DEFAULT '[]',
            summary TEXT,
            visibility TEXT NOT NULL DEFAULT 'internal',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            extensions_json TEXT,
            reference_task_ids_json TEXT,
            idempotency_key TEXT UNIQUE,
            created_at TEXT NOT NULL
        )
        """,
        # Tasks
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            context_id TEXT REFERENCES contexts(context_id),
            parent_task_id TEXT,
            title TEXT NOT NULL,
            user_goal TEXT,
            state TEXT NOT NULL DEFAULT 'submitted',
            priority TEXT NOT NULL DEFAULT 'medium',
            assigned_orchestrator_id TEXT,
            current_worker_id TEXT,
            status_message TEXT,
            progress_percent INTEGER DEFAULT 0,
            budget_json TEXT NOT NULL DEFAULT '{}',
            result_summary TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        )
        """,
        # Agenda items
        """
        CREATE TABLE IF NOT EXISTS agenda_items (
            agenda_item_id TEXT PRIMARY KEY,
            session_id TEXT REFERENCES boardroom_sessions(session_id),
            task_id TEXT REFERENCES tasks(task_id),
            title TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'open',
            turn_budget_json TEXT NOT NULL DEFAULT '{}',
            convergence_condition TEXT,
            final_arbiter_agent_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Decisions
        """
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(task_id),
            session_id TEXT REFERENCES boardroom_sessions(session_id),
            title TEXT NOT NULL,
            decision_summary TEXT,
            rationale_summary TEXT,
            decided_by TEXT,
            state TEXT NOT NULL DEFAULT 'proposed',
            scope_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Approvals
        """
        CREATE TABLE IF NOT EXISTS approvals (
            approval_id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(task_id),
            work_order_id TEXT,
            gate_type TEXT NOT NULL,
            risk_class TEXT,
            scope_json TEXT NOT NULL DEFAULT '{}',
            scope_hash TEXT NOT NULL,
            target_revision INTEGER NOT NULL DEFAULT 1,
            state TEXT NOT NULL DEFAULT 'pending',
            requested_by TEXT NOT NULL,
            approved_by TEXT,
            expires_at TEXT NOT NULL,
            idempotency_key TEXT UNIQUE,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Task events (event sourcing)
        """
        CREATE TABLE IF NOT EXISTS task_events (
            event_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            context_id TEXT,
            event_type TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            sequence INTEGER NOT NULL,
            correlation_id TEXT,
            causation_id TEXT,
            idempotency_key TEXT UNIQUE,
            schema_version INTEGER NOT NULL DEFAULT 1,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            UNIQUE(task_id, sequence)
        )
        """,
        # Work orders
        """
        CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL REFERENCES tasks(task_id),
            parent_work_order_id TEXT,
            worker_kind TEXT NOT NULL,
            capability_required TEXT,
            instruction_summary TEXT,
            instruction_path TEXT,
            state TEXT NOT NULL DEFAULT 'ready',
            lease_owner TEXT,
            lease_expires_at TEXT,
            heartbeat_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            result_summary TEXT,
            error_summary TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        )
        """,
        # Bus queue
        """
        CREATE TABLE IF NOT EXISTS bus_queue (
            queue_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            key TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            state TEXT NOT NULL DEFAULT 'ready',
            lease_owner TEXT,
            lease_expires_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            available_at TEXT NOT NULL,
            idempotency_key TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_queue_topic_idempotency
        ON bus_queue(topic, idempotency_key) WHERE idempotency_key IS NOT NULL
        """,
        # Artifacts
        """
        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            task_id TEXT REFERENCES tasks(task_id),
            work_order_id TEXT REFERENCES work_orders(work_order_id),
            name TEXT NOT NULL,
            description TEXT,
            kind TEXT NOT NULL,
            media_type TEXT,
            uri TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'internal',
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            provenance_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT,
            created_at TEXT NOT NULL
        )
        """,
        # Projection offsets
        """
        CREATE TABLE IF NOT EXISTS projection_offsets (
            projection_name TEXT NOT NULL,
            task_id TEXT,
            last_event_sequence INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            error_summary TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (projection_name, task_id)
        )
        """,
        # Dashboard messages
        """
        CREATE TABLE IF NOT EXISTS dashboard_messages (
            dashboard_id TEXT PRIMARY KEY,
            task_id TEXT,
            platform TEXT NOT NULL,
            channel_id TEXT,
            thread_id TEXT,
            message_id TEXT,
            revision INTEGER NOT NULL DEFAULT 1,
            last_rendered_hash TEXT,
            last_event_sequence INTEGER NOT NULL DEFAULT 0,
            last_rendered_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        # Seed default agents
        """
        INSERT OR IGNORE INTO agent_cards (agent_id, name, persona_type, description, version, capabilities_json, skills_json, protocols_json, registry_metadata_json, status, created_at, updated_at)
        VALUES
            ('chair', 'Chair', 'orchestrator', 'Session chair and facilitator', '0.1.0', '["facilitation", "agenda_management"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('pm', 'PM', 'planner', 'Project manager and requirements analyst', '0.1.0', '["planning", "requirements", "scoping"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('researcher', 'Researcher', 'analyst', 'Information researcher and fact checker', '0.1.0', '["research", "fact_checking"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('engineer', 'Engineer', 'implementer', 'Software engineer and builder', '0.1.0', '["coding", "architecture", "testing"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('critic', 'Critic', 'reviewer', 'Critical reviewer and quality gate', '0.1.0', '["review", "quality_gate"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('scribe', 'Scribe', 'recorder', 'Documentation and record keeper', '0.1.0', '["documentation", "summarization"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('qa', 'QA', 'tester', 'Quality assurance and test engineer', '0.1.0', '["testing", "verification"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('ops', 'Ops', 'operator', 'Operations and infrastructure', '0.1.0', '["deployment", "monitoring"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('security_auditor', 'Security Auditor', 'auditor', 'Security and compliance reviewer', '0.1.0', '["security", "compliance"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('cost_controller', 'Cost Controller', 'economist', 'Budget and cost oversight', '0.1.0', '["budgeting", "cost_tracking"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('memory_curator', 'Memory Curator', 'archivist', 'Knowledge and memory management', '0.1.0', '["memory", "knowledge_management"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('painter', 'Painter', 'artist', 'Visual design and image generation', '0.1.0', '["visual_design", "image_generation"]', '[]', '["boardroom", "painter"]', '{"seed": true}', 'active', datetime('now'), datetime('now')),
            ('system', 'System', 'system', 'System-level agent for infrastructure tasks', '0.1.0', '["system", "maintenance"]', '[]', '["boardroom"]', '{"seed": true}', 'active', datetime('now'), datetime('now'))
        """,
    ],
]


APPROVAL_GATE_TYPES = frozenset({
    "repo_write",
    "local_artifact_write",
    "external_post",
    "mail_calendar_write",
    "credential_access",
    "discord_config",
    "gateway_systemd",
    "cost_budget",
    "image_generation",
    "public_publication",
    "destructive_action",
    "human_input",
})


def apply_migrations(conn) -> int:
    """Apply pending migrations. Returns current schema version."""
    import sqlite3
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    try:
        cur = conn.execute("SELECT MAX(version) FROM schema_migrations")
        row = cur.fetchone()
        current_version = row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        current_version = 0

    for version, statements in enumerate(MIGRATIONS, start=1):
        if version <= current_version:
            continue
        for stmt in statements:
            conn.execute(stmt)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, f"migration_{version}", now),
        )
        conn.commit()
        current_version = version

    return current_version


def get_schema_version(conn) -> int:
    import sqlite3
    try:
        cur = conn.execute("SELECT MAX(version) FROM schema_migrations")
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0
