"""Deterministic Zeus OS worker fixtures.

These workers are intentionally local and side-effect bounded. They process
canonical SQLite queue/work_order rows and registered filesystem artifacts only;
no live external agent, Hermes, Discord, browser, or systemd boundary is touched.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import artifacts, events, queue, store


def run_deterministic_once(
    conn: sqlite3.Connection,
    artifact_root: Path,
    *,
    kind: str = "deterministic",
    lease_owner: str | None = None,
) -> dict[str, Any]:
    """Claim one work item and complete it with deterministic evidence."""
    owner = lease_owner or f"cli-worker-{kind}"
    topic = f"worker.{kind}"
    claimed = queue.claim_next(conn, topic, owner, lease_seconds=300)
    if not claimed:
        return {"ok": True, "action": "no_work"}

    payload = claimed["payload"]
    work_order_id = payload.get("work_order_id")
    task_id = payload.get("task_id")
    if not task_id:
        raise ValueError("deterministic worker payload requires task_id")

    evidence = {
        "worker_kind": kind,
        "lease_owner": owner,
        "queue_id": claimed["queue_id"],
        "task_id": task_id,
        "work_order_id": work_order_id,
        "action": "deterministic_processed",
    }
    artifact_record = artifacts.write_artifact(
        artifact_root,
        task_id,
        "deterministic-worker-result.json",
        "worker_result",
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        work_order_id=work_order_id,
        media_type="application/json",
        description="Deterministic worker fixture output",
        visibility="internal",
        created_by=owner,
        provenance={"mode": "deterministic_fixture", "topic": topic},
    )
    artifact_id = artifacts.register_artifact(conn, artifact_record)
    event = events.append_event(
        conn,
        task_id=task_id,
        event_type="worker.completed",
        actor_type="worker",
        actor_id=owner,
        payload={"work_order_id": work_order_id, "queue_id": claimed["queue_id"], "artifact_id": artifact_id},
        correlation_id=work_order_id,
    )
    result = {**evidence, "artifact_id": artifact_id, "event_id": event["event_id"]}
    queue.ack(conn, claimed["queue_id"], owner, work_order_result=result)
    return {"ok": True, **result}
