"""Hermes Zeus Gateway plugin — dry-run boardroom projection adapter."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def load_plugin(config: dict[str, Any]) -> "ZeusGatewayPlugin":
    return ZeusGatewayPlugin(config)


class ZeusGatewayPlugin:
    def __init__(self, config: dict[str, Any]) -> None:
        self.dry_run = config.get("dry_run", True)
        self.db_path = config.get("zeus_db_path", "")
        self.poll_seconds = config.get("projection_poll_seconds", 30)
        self.max_cards = config.get("max_cards_per_batch", 10)
        self.allowed_channels = set(config.get("allowed_channels", []))
        self._conn: sqlite3.Connection | None = None

    def _ensure_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            if not self.db_path:
                self.db_path = str(Path("state/zeus_os.db").resolve())
            if not Path(self.db_path).exists():
                raise FileNotFoundError(f"Zeus DB not found: {self.db_path}")
            self._conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def render_session_status_card(self, session_id: str) -> dict[str, Any]:
        conn = self._ensure_connection()
        cur = conn.execute(
            """
            SELECT s.session_id, s.title, s.status, s.current_round, s.max_rounds,
                   COUNT(DISTINCT p.agent_id) as participant_count
            FROM boardroom_sessions s
            LEFT JOIN boardroom_participants p ON p.session_id = s.session_id
            WHERE s.session_id = ?
            GROUP BY s.session_id
            """,
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Session not found"}

        card = {
            "type": "session_status",
            "session_id": row["session_id"],
            "title": row["title"],
            "status": row["status"],
            "round": f"{row['current_round']}/{row['max_rounds']}",
            "participants": row["participant_count"],
            "dry_run": self.dry_run,
        }
        return {"ok": True, "card": card}

    def render_active_agents_card(self) -> dict[str, Any]:
        conn = self._ensure_connection()
        cur = conn.execute(
            """
            SELECT w.worker_id, w.agent_id, w.display_name, w.status, w.current_work_order_id, w.heartbeat_at
            FROM worker_agents w
            WHERE w.status != 'retired'
            ORDER BY w.heartbeat_at DESC
            LIMIT ?
            """,
            (self.max_cards,),
        )
        agents = []
        for row in cur.fetchall():
            agents.append({
                "worker_id": row["worker_id"],
                "agent_id": row["agent_id"],
                "display_name": row["display_name"],
                "status": row["status"],
                "current_work_order_id": row["current_work_order_id"],
                "heartbeat_at": row["heartbeat_at"],
            })
        return {"ok": True, "type": "active_agents", "agents": agents, "dry_run": self.dry_run}

    def render_approval_card(self, approval_id: str) -> dict[str, Any]:
        conn = self._ensure_connection()
        cur = conn.execute(
            """
            SELECT approval_id, gate_type, risk_class, scope_json, state, requested_by, expires_at
            FROM approvals WHERE approval_id = ?
            """,
            (approval_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Approval not found"}

        card = {
            "type": "approval",
            "approval_id": row["approval_id"],
            "gate_type": row["gate_type"],
            "risk_class": row["risk_class"],
            "state": row["state"],
            "requested_by": row["requested_by"],
            "expires_at": row["expires_at"],
            "dry_run": self.dry_run,
        }
        return {"ok": True, "card": card}

    def poll_projections(self) -> list[dict[str, Any]]:
        if self.dry_run:
            return [{"action": "noop", "reason": "dry_run_mode"}]
        return [{"action": "noop", "reason": "live_mode_not_implemented"}]

    def health_check(self) -> dict[str, Any]:
        try:
            conn = self._ensure_connection()
            row = conn.execute("SELECT COUNT(*) FROM agent_cards").fetchone()
            return {
                "ok": True,
                "agent_count": row[0],
                "dry_run": self.dry_run,
                "db_path": self.db_path,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
