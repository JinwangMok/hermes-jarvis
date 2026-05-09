"""Minerva -> ZeusOS canonical boardroom runtime materialization.

This adapter keeps Minerva's Discord/workflow artifacts and the canonical ZeusOS
A2A/Boardroom SQLite projection connected without touching live Hermes runtime.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .zeus_os import store

ADAPTER_VERSION = "minerva_boardroom_runtime/v1"
DEFAULT_AGENT_MANIFESTS: tuple[dict[str, Any], ...] = (
    {"name": "apollo", "spec": {"persona": "review and goal-alignment oracle", "role": "reviewer", "shim": "hermes", "kanban": {}, "selfJustification": {}}},
    {"name": "artemis", "spec": {"persona": "research scout", "role": "research_scout", "shim": "hermes", "kanban": {}, "selfJustification": {}}},
    {"name": "athena", "spec": {"persona": "plan critic and strategy challenger", "role": "plan_critic", "shim": "hermes", "kanban": {}, "selfJustification": {}}},
    {"name": "boramae", "spec": {"persona": "Discord conversation surface", "role": "discord_conversation", "shim": "hermes", "kanban": {}, "selfJustification": {}}},
    {"name": "hephaestus", "spec": {"persona": "bounded implementation builder", "role": "builder", "shim": "hermes", "kanban": {}, "selfJustification": {}}},
    {"name": "janus", "spec": {"persona": "memory and evolution gatekeeper", "role": "memory_evolution", "shim": "hermes", "kanban": {}, "selfJustification": {}}},
    {"name": "minerva", "spec": {"persona": "command governor", "role": "command_governor", "shim": "hermes", "kanban": {}, "selfJustification": {}}},
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)


def _short_text(value: str, limit: int = 240) -> str:
    text = str(value).replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _ids(run_id: str) -> tuple[str, str]:
    suffix = _digest(run_id)
    return f"ctx_minerva_{suffix}", f"ses_minerva_{suffix}"


def _message_id(run_id: str, ordinal: int) -> str:
    return f"msg_minerva_{_digest(run_id)}_{ordinal:04d}"


def _load_agent_manifests(agents_dir: Path) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    if not agents_dir.exists():
        return [{"path": None, "name": manifest["name"], "spec": dict(manifest["spec"]), "raw": manifest} for manifest in DEFAULT_AGENT_MANIFESTS]
    for path in sorted(agents_dir.glob("*.yaml")):
        if path.is_symlink() or not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        metadata = data.get("metadata") or {}
        spec = data.get("spec") or {}
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            continue
        name = str(metadata.get("name") or path.stem).strip()
        if not name:
            continue
        manifests.append({"path": path, "name": name, "spec": spec, "raw": data})
    return manifests or [{"path": None, "name": manifest["name"], "spec": dict(manifest["spec"]), "raw": manifest} for manifest in DEFAULT_AGENT_MANIFESTS]


@dataclass(frozen=True)
class MinervaBoardroomAdapter:
    """Materialize Minerva workflow events into the canonical ZeusOS store."""

    workspace_root: Path
    agents_dir: Path | None = None

    @classmethod
    def from_workspace(cls, workspace_root: Path) -> "MinervaBoardroomAdapter":
        repo_root = Path(__file__).resolve().parents[2]
        agents_dir = repo_root / "agents"
        return cls(workspace_root=workspace_root, agents_dir=agents_dir)

    @property
    def db_path(self) -> Path:
        return self.workspace_root / "state" / "zeus_os.db"

    def record_start(self, run: dict[str, Any], origin: dict[str, Any]) -> dict[str, Any]:
        run_id = str(run["run_id"])
        context_id, session_id = _ids(run_id)
        with self._connect() as conn:
            with store.transaction(conn):
                self._upsert_context(conn, context_id, run, origin)
                self._upsert_session(conn, session_id, context_id, run, origin)
                self._upsert_participants(conn, session_id, run_id)
                self._insert_message_once(
                    conn,
                    run_id=run_id,
                    context_id=context_id,
                    ordinal=0,
                    idempotency_key=f"minerva:{run_id}:start",
                    role="user",
                    sender_agent_id=None,
                    parts=[{"type": "text", "text": str(run.get("goal") or "")}],
                    summary=_short_text(str(run.get("goal") or "")),
                    metadata={
                        "adapter": ADAPTER_VERSION,
                        "minerva_run_id": run_id,
                        "minerva_stage": "start",
                        "boardroom_session_id": session_id,
                    },
                )
            return self.read_summary(run_id) or {"adapter": ADAPTER_VERSION, "session_id": session_id}

    def record_turn(self, run: dict[str, Any], message: str, turn_index: int) -> dict[str, Any]:
        run_id = str(run["run_id"])
        context_id, session_id = _ids(run_id)
        with self._connect() as conn:
            with store.transaction(conn):
                self._ensure_session_minimal(conn, context_id, session_id, run)
                self._insert_message_once(
                    conn,
                    run_id=run_id,
                    context_id=context_id,
                    ordinal=turn_index,
                    idempotency_key=f"minerva:{run_id}:turn:{turn_index}",
                    role="user",
                    sender_agent_id=None,
                    parts=[{"type": "text", "text": message}],
                    summary=_short_text(message),
                    metadata={
                        "adapter": ADAPTER_VERSION,
                        "minerva_run_id": run_id,
                        "minerva_stage": "turn",
                        "turn_index": turn_index,
                        "boardroom_session_id": session_id,
                    },
                )
            return self.read_summary(run_id) or {"adapter": ADAPTER_VERSION, "session_id": session_id}

    def record_seed(self, run: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
        run_id = str(run["run_id"])
        seed_version = int(seed.get("version") or run.get("seed_version") or 1)
        context_id, session_id = _ids(run_id)
        with self._connect() as conn:
            if self._seed_already_materialized(conn, session_id, run_id, seed_version):
                return self.read_summary(run_id) or {"adapter": ADAPTER_VERSION, "session_id": session_id}
            with store.transaction(conn):
                self._ensure_session_minimal(conn, context_id, session_id, run)
                now = store.now_utc()
                row = conn.execute("SELECT metadata_json FROM boardroom_sessions WHERE session_id = ?", (session_id,)).fetchone()
                existing_metadata = json.loads(row["metadata_json"]) if row is not None else {}
                existing_metadata.update({
                    "adapter": ADAPTER_VERSION,
                    "minerva_run_id": run_id,
                    "minerva_phase": "seeded",
                    "seed_version": seed_version,
                })
                conn.execute(
                    """
                    UPDATE boardroom_sessions
                    SET metadata_json = ?, updated_at = ?, revision = revision + 1
                    WHERE session_id = ?
                    """,
                    (
                        _json(existing_metadata),
                        now,
                        session_id,
                    ),
                )
                self._insert_message_once(
                    conn,
                    run_id=run_id,
                    context_id=context_id,
                    ordinal=999,
                    idempotency_key=f"minerva:{run_id}:seed:v{seed_version}",
                    role="assistant",
                    sender_agent_id="minerva",
                    parts=[
                        {"type": "text", "text": f"Minerva seed v{seed_version} materialized"},
                        {"type": "artifact_ref", "uri": f"data/minerva/{run_id}/seed.json"},
                        {"type": "artifact_ref", "uri": f"data/minerva/{run_id}/workflow_design.json"},
                    ],
                    summary=f"Minerva seed v{seed_version} materialized",
                    metadata={
                        "adapter": ADAPTER_VERSION,
                        "minerva_run_id": run_id,
                        "minerva_stage": "seed",
                        "seed_version": seed_version,
                        "boardroom_session_id": session_id,
                    },
                )
            return self.read_summary(run_id) or {"adapter": ADAPTER_VERSION, "session_id": session_id}

    def read_summary(self, run_id: str) -> dict[str, Any] | None:
        context_id, session_id = _ids(run_id)
        if not self.db_path.exists():
            return None
        with self._connect() as conn:
            session = conn.execute("SELECT * FROM boardroom_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if session is None:
                return None
            participant_count = conn.execute(
                "SELECT COUNT(*) FROM boardroom_participants WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            message_count = conn.execute("SELECT COUNT(*) FROM messages WHERE context_id = ?", (context_id,)).fetchone()[0]
        return {
            "adapter": ADAPTER_VERSION,
            "db_path": str(self.db_path.relative_to(self.workspace_root)),
            "context_id": context_id,
            "session_id": session_id,
            "participant_count": participant_count,
            "message_count": message_count,
        }

    def read_snapshot(self, run_id: str) -> dict[str, Any] | None:
        context_id, session_id = _ids(run_id)
        if not self.db_path.exists():
            return None
        with self._connect() as conn:
            session = conn.execute("SELECT * FROM boardroom_sessions WHERE session_id = ?", (session_id,)).fetchone()
            if session is None:
                return None
            participants = conn.execute(
                "SELECT * FROM boardroom_participants WHERE session_id = ? ORDER BY agent_id",
                (session_id,),
            ).fetchall()
            messages = conn.execute(
                "SELECT * FROM messages WHERE context_id = ? ORDER BY created_at, message_id",
                (context_id,),
            ).fetchall()
        return {
            "adapter": ADAPTER_VERSION,
            "session": self._row_to_dict(session),
            "participants": [self._row_to_dict(row) for row in participants],
            "messages": [self._row_to_dict(row) for row in messages],
        }

    def _connect(self) -> sqlite3.Connection:
        return store.init_store(store.StoreConfig.from_workspace(str(self.workspace_root)))

    def _seed_already_materialized(self, conn: sqlite3.Connection, session_id: str, run_id: str, seed_version: int) -> bool:
        row = conn.execute("SELECT metadata_json FROM boardroom_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return False
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            return False
        if metadata.get("minerva_run_id") != run_id or int(metadata.get("seed_version") or 0) != seed_version:
            return False
        key = f"minerva:{run_id}:seed:v{seed_version}"
        return conn.execute("SELECT 1 FROM messages WHERE idempotency_key = ?", (key,)).fetchone() is not None

    def _upsert_context(self, conn: sqlite3.Connection, context_id: str, run: dict[str, Any], origin: dict[str, Any]) -> None:
        now = store.now_utc()
        conn.execute(
            """
            INSERT INTO contexts (context_id, origin_platform, origin_channel_id, origin_thread_id, origin_message_id, title, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
            ON CONFLICT(context_id) DO UPDATE SET
                origin_platform=excluded.origin_platform,
                origin_channel_id=excluded.origin_channel_id,
                origin_thread_id=excluded.origin_thread_id,
                origin_message_id=excluded.origin_message_id,
                title=excluded.title,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            (
                context_id,
                origin.get("platform") or run.get("origin_platform") or "cli",
                origin.get("channel_id") or run.get("origin_channel_id"),
                origin.get("thread_id") or run.get("origin_thread_id"),
                (origin.get("thread") or {}).get("message_id"),
                _short_text(str(run.get("goal") or ""), 120),
                _json({"adapter": ADAPTER_VERSION, "minerva_run_id": run["run_id"]}),
                now,
                now,
            ),
        )

    def _upsert_session(self, conn: sqlite3.Connection, session_id: str, context_id: str, run: dict[str, Any], origin: dict[str, Any]) -> None:
        now = store.now_utc()
        existing = conn.execute("SELECT metadata_json FROM boardroom_sessions WHERE session_id = ?", (session_id,)).fetchone()
        try:
            metadata = json.loads(existing["metadata_json"] or "{}") if existing is not None else {}
        except json.JSONDecodeError:
            metadata = {}
        metadata.update({
            "adapter": ADAPTER_VERSION,
            "minerva_run_id": run["run_id"],
            "minerva_phase": run.get("phase"),
            "origin_platform": origin.get("platform") or run.get("origin_platform"),
            "origin_channel_id": origin.get("channel_id") or run.get("origin_channel_id"),
            "origin_thread_id": origin.get("thread_id") or run.get("origin_thread_id"),
        })
        conn.execute(
            """
            INSERT INTO boardroom_sessions (
                session_id, context_id, task_id, title, status, max_rounds, current_round,
                final_arbiter_agent_id, budget_json, metadata_json, revision, created_at, updated_at
            ) VALUES (?, ?, NULL, ?, 'open', 5, 0, 'minerva', '{}', ?, 1, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                context_id=excluded.context_id,
                title=excluded.title,
                final_arbiter_agent_id=excluded.final_arbiter_agent_id,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at,
                revision=boardroom_sessions.revision + 1
            """,
            (session_id, context_id, f"Minerva: {_short_text(str(run.get('goal') or ''), 160)}", _json(metadata), now, now),
        )

    def _ensure_session_minimal(self, conn: sqlite3.Connection, context_id: str, session_id: str, run: dict[str, Any]) -> None:
        origin = {
            "platform": run.get("origin_platform"),
            "channel_id": run.get("origin_channel_id"),
            "thread_id": run.get("origin_thread_id"),
            "thread": {},
        }
        self._upsert_context(conn, context_id, run, origin)
        self._upsert_session(conn, session_id, context_id, run, origin)
        self._upsert_participants(conn, session_id, str(run["run_id"]))

    def _upsert_participants(self, conn: sqlite3.Connection, session_id: str, run_id: str) -> None:
        for manifest in _load_agent_manifests(self.agents_dir or Path()):
            name = manifest["name"]
            spec = manifest["spec"]
            role = str(spec.get("role") or "participant")
            now = store.now_utc()
            conn.execute(
                """
                INSERT INTO agent_cards (
                    agent_id, name, persona_type, description, version, capabilities_json, skills_json,
                    protocols_json, registry_metadata_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, '0.1.0', ?, ?, ?, ?, 'active', ?, ?)
                ON CONFLICT(agent_id) DO NOTHING
                """,
                (
                    name,
                    name.title(),
                    role,
                    str(spec.get("persona") or ""),
                    _json([]),
                    _json([]),
                    _json(["minerva_boardroom_runtime"]),
                    _json({
                        "adapter": ADAPTER_VERSION,
                        "manifest_path": str(manifest["path"].relative_to(manifest["path"].parents[1])) if manifest.get("path") is not None else "builtin:default-minerva-roster",
                        "shim": spec.get("shim"),
                        "kanban": spec.get("kanban") or {},
                        "selfJustification": spec.get("selfJustification") or {},
                    }),
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO boardroom_participants (session_id, agent_id, role, status, turn_budget_json, metadata_json, joined_at, updated_at)
                VALUES (?, ?, ?, 'active', '{}', ?, ?, ?)
                ON CONFLICT(session_id, agent_id) DO UPDATE SET
                    role=excluded.role,
                    status=excluded.status,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    session_id,
                    name,
                    role,
                    _json({"adapter": ADAPTER_VERSION, "minerva_run_id": run_id, "manifest_role": role}),
                    now,
                    now,
                ),
            )

    def _insert_message_once(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        context_id: str,
        ordinal: int,
        idempotency_key: str,
        role: str,
        sender_agent_id: str | None,
        parts: list[dict[str, Any]],
        summary: str,
        metadata: dict[str, Any],
    ) -> None:
        now = store.now_utc()
        conn.execute(
            """
            INSERT INTO messages (
                message_id, context_id, task_id, role, sender_agent_id, parts_json, summary,
                visibility, metadata_json, extensions_json, reference_task_ids_json, idempotency_key, created_at
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, 'internal', ?, NULL, NULL, ?, ?)
            ON CONFLICT(idempotency_key) DO NOTHING
            """,
            (
                _message_id(run_id, ordinal),
                context_id,
                role,
                sender_agent_id,
                _json(parts),
                summary,
                _json(metadata),
                idempotency_key,
                now,
            ),
        )

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in row.keys()}
