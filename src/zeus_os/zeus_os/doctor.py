"""Health checks and diagnostics for Zeus OS."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import artifacts, safety, schema, store


def run_diagnostics(config: store.StoreConfig) -> dict[str, Any]:
    results: dict[str, Any] = {
        "ok": True,
        "db_exists": False,
        "schema_version": 0,
        "wal_mode": False,
        "foreign_keys": False,
        "artifact_root_writable": False,
        "artifact_issues": {},
        "queue_state": {},
        "expired_leases": [],
        "stale_workers": [],
        "dead_letters": [],
        "pending_approvals": [],
        "projection_lag": [],
        "secret_findings": [],
        "config_paths_ok": True,
    }

    db_path = Path(config.db_path)
    results["db_exists"] = db_path.exists()
    if not results["db_exists"]:
        results["ok"] = False
        return results

    try:
        conn = store.init_store(config)
    except Exception as exc:
        results["ok"] = False
        results["db_error"] = str(exc)
        return results

    with conn:
        # Schema version
        results["schema_version"] = schema.get_schema_version(conn)

        # Pragmas
        wal_row = conn.execute("PRAGMA journal_mode").fetchone()
        results["wal_mode"] = wal_row is not None and wal_row[0].upper() == "WAL"
        fk_row = conn.execute("PRAGMA foreign_keys").fetchone()
        results["foreign_keys"] = fk_row is not None and bool(fk_row[0])

        if not results["wal_mode"] or not results["foreign_keys"]:
            results["ok"] = False

        # Artifact root
        artifact_root = Path(config.artifact_root)
        artifact_root.mkdir(parents=True, exist_ok=True)
        results["artifact_root_writable"] = _is_writable(artifact_root)
        if not results["artifact_root_writable"]:
            results["ok"] = False

        # Artifact reconciliation
        try:
            results["artifact_issues"] = artifacts.reconcile_artifacts(conn, artifact_root)
            if any(results["artifact_issues"].values()):
                results["ok"] = False
        except Exception as exc:
            results["artifact_issues"]["error"] = str(exc)
            results["ok"] = False

        # Queue state
        from . import queue
        results["queue_state"] = queue.list_queue_state(conn)

        # Expired leases
        now = store.now_utc()
        cur = conn.execute(
            """
            SELECT queue_id, topic, lease_owner, lease_expires_at
            FROM bus_queue WHERE state = 'leased' AND lease_expires_at < ?
            """,
            (now,),
        )
        results["expired_leases"] = [dict(row) for row in cur.fetchall()]

        # Stale workers
        cur = conn.execute(
            """
            SELECT worker_id, agent_id, display_name, heartbeat_at
            FROM worker_agents
            WHERE heartbeat_at IS NULL OR heartbeat_at < ?
            """,
            (now,),
        )
        results["stale_workers"] = [dict(row) for row in cur.fetchall()]

        # Dead letters
        results["dead_letters"] = queue.list_dead_letters(conn)

        # Pending/stale approvals
        cur = conn.execute(
            """
            SELECT approval_id, gate_type, state, expires_at, requested_by
            FROM approvals
            WHERE state = 'pending' AND expires_at < ?
            """,
            (now,),
        )
        results["pending_approvals"] = [dict(row) for row in cur.fetchall()]

        # Projection lag
        cur = conn.execute(
            """
            SELECT projection_name, task_id, last_event_sequence, status, error_summary
            FROM projection_offsets
            """
        )
        results["projection_lag"] = [dict(row) for row in cur.fetchall()]

        # Secret scan on messages and artifacts
        scan_sources = [
            ("messages", "parts_json", conn.execute("SELECT parts_json FROM messages")),
            ("artifacts", "metadata_json", conn.execute("SELECT metadata_json FROM artifacts")),
        ]
        for table, col, cur in scan_sources:
            for row in cur.fetchall():
                text = row[0] or ""
                findings = safety.scan_for_secrets(text)
                for finding in findings:
                    results["secret_findings"].append({
                        "table": table,
                        "column": col,
                        "pattern_index": finding["pattern_index"],
                        "position": finding["start"],
                    })
        if results["secret_findings"]:
            results["ok"] = False

        # Config paths rooted under workspace
        workspace = Path(config.workspace_root).resolve()
        for path_str in [config.db_path, config.artifact_root]:
            p = Path(path_str).resolve()
            try:
                p.relative_to(workspace)
            except ValueError:
                results["config_paths_ok"] = False
                results["ok"] = False

    return results


def _is_writable(path: Path) -> bool:
    try:
        test_file = path / ".zeus_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return True
    except (OSError, PermissionError):
        return False
