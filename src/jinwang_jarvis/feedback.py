from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig

VALID_DECISIONS = {"allow": "allowed", "reject": "rejected"}
VALID_REASON_CODES = {
    "spam",
    "low-value",
    "duplicate",
    "already-scheduled",
    "not-attending",
    "wrong-time",
    "wrong-classification",
    "fyi-only",
    "other",
}


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _artifact_timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _load_proposal(conn: sqlite3.Connection, proposal_id: str) -> dict:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT proposal_id, source_message_id, title, start_ts, end_ts, location,
               description_md, confidence, status, dedup_key, reason_json,
               created_at, resolved_at
        FROM event_proposals
        WHERE proposal_id = ?
        """,
        (proposal_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown proposal_id: {proposal_id}")
    proposal = dict(row)
    if proposal.get("reason_json"):
        proposal["reason_json"] = json.loads(proposal["reason_json"])
    return proposal


def record_proposal_feedback(
    config: PipelineConfig,
    proposal_id: str,
    decision: str,
    reason_code: str,
    freeform_note: str | None = None,
    *,
    recorded_at: datetime | None = None,
) -> dict:
    bootstrap_workspace(config)
    normalized_decision = decision.strip().lower()
    if normalized_decision not in VALID_DECISIONS:
        raise ValueError(f"Unsupported decision: {decision}")
    if not reason_code or not reason_code.strip():
        raise ValueError("reason_code must be provided")
    normalized_reason = reason_code.strip().lower()
    if normalized_reason not in VALID_REASON_CODES:
        raise ValueError(f"Unsupported reason_code: {reason_code}")

    moment = recorded_at or _utc_now()
    moment = moment.astimezone(UTC).replace(microsecond=0)
    recorded_at_text = moment.isoformat()
    resolved_status = VALID_DECISIONS[normalized_decision]
    artifact_dir = config.workspace_root / "data" / "feedback"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"feedback-{proposal_id}-{_artifact_timestamp(moment)}.json"

    with sqlite3.connect(config.database_path) as conn:
        proposal = _load_proposal(conn, proposal_id)
        conn.execute(
            """
            INSERT OR REPLACE INTO proposal_feedback (
                proposal_id, decision, reason_code, freeform_note, recorded_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (proposal_id, normalized_decision, normalized_reason, freeform_note, recorded_at_text),
        )
        conn.execute(
            """
            UPDATE event_proposals
            SET status = ?, resolved_at = ?
            WHERE proposal_id = ?
            """,
            (resolved_status, recorded_at_text, proposal_id),
        )
        conn.commit()

    artifact = {
        "proposal_id": proposal_id,
        "decision": normalized_decision,
        "reason_code": normalized_reason,
        "freeform_note": freeform_note,
        "recorded_at": recorded_at_text,
        "updated_status": resolved_status,
        "proposal": proposal,
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoints = {}
    if config.checkpoints_path.exists():
        checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8"))
    checkpoints.setdefault("feedback", {})
    checkpoints["feedback"][proposal_id] = {
        "decision": normalized_decision,
        "reason_code": normalized_reason,
        "recorded_at": recorded_at_text,
        "artifact_file": artifact_path.name,
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "proposal_id": proposal_id,
        "decision": normalized_decision,
        "updated_status": resolved_status,
        "recorded_at": recorded_at_text,
        "artifact_path": artifact_path,
    }
