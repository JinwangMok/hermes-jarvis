from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _load_recent_proposals(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT proposal_id, title, start_ts, confidence, status, source_message_id
        FROM event_proposals
        ORDER BY created_at DESC, confidence DESC, proposal_id ASC
        LIMIT 10
        """
    ).fetchall()


def _load_label_counts(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    rows = conn.execute(
        """
        SELECT label, COUNT(*) AS label_count
        FROM message_labels
        GROUP BY label
        ORDER BY label_count DESC, label ASC
        """
    ).fetchall()
    return [(str(label), int(count)) for label, count in rows]


def _load_notable_messages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT m.message_id, m.subject, m.from_addr, m.sent_at, ml.label, ml.score
        FROM messages AS m
        JOIN message_labels AS ml ON ml.message_id = m.message_id
        WHERE ml.label IN ('advisor-request', 'meeting', 'ta', 'lab')
        ORDER BY ml.score DESC, COALESCE(m.sent_at, '' ) DESC, m.message_id ASC
        LIMIT 12
        """
    ).fetchall()


def generate_digest(config: PipelineConfig, proposal_result: dict | None = None, *, as_of: datetime | None = None) -> dict:
    bootstrap_workspace(config)
    moment = (as_of or _utc_now()).astimezone(UTC).replace(microsecond=0)
    artifact_dir = config.workspace_root / "data" / "digests"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"digest-{moment.strftime('%Y%m%dT%H%M%SZ')}.md"

    with sqlite3.connect(config.database_path) as conn:
        recent_proposals = _load_recent_proposals(conn)
        label_counts = _load_label_counts(conn)
        notable_messages = _load_notable_messages(conn)

    lines = [
        f"# Jarvis Digest — {moment.isoformat()}",
        "",
        "## Pipeline summary",
        f"- total labels tracked: {sum(count for _, count in label_counts)}",
    ]
    if proposal_result is not None:
        lines.extend(
            [
                f"- proposal run generated at: {proposal_result.get('generated_at', 'n/a')}",
                f"- proposal_count: {proposal_result.get('proposal_count', 0)}",
                f"- action_signal_count: {proposal_result.get('action_signal_count', 0)}",
                f"- suppressed_count: {proposal_result.get('suppressed_count', 0)}",
            ]
        )

    lines.extend(["", "## Message label counts"])
    if label_counts:
        lines.extend(f"- {label}: {count}" for label, count in label_counts)
    else:
        lines.append("- No classified messages yet.")

    lines.extend(["", "## Recent proposals"])
    if recent_proposals:
        for proposal in recent_proposals:
            lines.append(
                "- {title} (`{proposal_id}`) — status: {status}, confidence: {confidence:.2f}, start: {start_ts}, source: {source_message_id}".format(
                    title=proposal["title"],
                    proposal_id=proposal["proposal_id"],
                    status=proposal["status"],
                    confidence=float(proposal["confidence"]),
                    start_ts=proposal["start_ts"] or "n/a",
                    source_message_id=proposal["source_message_id"] or "n/a",
                )
            )
    else:
        lines.append("- No proposals available.")

    lines.extend(["", "## Notable messages"])
    if notable_messages:
        for row in notable_messages:
            lines.append(
                "- [{label}] {subject} — from {from_addr} ({sent_at}) `message:{message_id}`".format(
                    label=row["label"],
                    subject=row["subject"] or "(no subject)",
                    from_addr=row["from_addr"] or "unknown",
                    sent_at=row["sent_at"] or "n/a",
                    message_id=row["message_id"],
                )
            )
    else:
        lines.append("- No notable messages found.")

    artifact_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    checkpoints = {}
    if config.checkpoints_path.exists():
        checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8"))
    checkpoints.setdefault("digest", {})
    checkpoints["digest"]["latest"] = {
        "generated_at": moment.isoformat(),
        "artifact_file": artifact_path.name,
        "proposal_count": int(proposal_result.get("proposal_count", 0)) if proposal_result else 0,
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "artifact_path": artifact_path,
        "generated_at": moment.isoformat(),
        "recent_proposal_count": len(recent_proposals),
        "label_count": len(label_counts),
        "notable_message_count": len(notable_messages),
    }
