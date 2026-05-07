from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _normalize_as_of(as_of: datetime | None) -> datetime:
    if as_of is None:
        return _utc_now()
    return as_of.astimezone(UTC).replace(microsecond=0)


def _collect_label_counts(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    rows = conn.execute(
        """
        SELECT label, COUNT(*) AS label_count
        FROM message_labels
        GROUP BY label
        ORDER BY label_count DESC, label ASC
        """
    ).fetchall()
    return [(str(label), int(label_count)) for label, label_count in rows]


def _collect_unresolved_proposals(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT proposal_id, title, start_ts, confidence, status, source_message_id
        FROM event_proposals
        WHERE resolved_at IS NULL AND status NOT IN ('allowed', 'rejected')
        ORDER BY confidence DESC, created_at ASC, proposal_id ASC
        """
    ).fetchall()


def _collect_calendar_events(conn: sqlite3.Connection, week_start: str, week_end: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT event_id, summary, start_ts, end_ts, location, status
        FROM calendar_events
        WHERE COALESCE(start_ts, '') >= ? AND COALESCE(start_ts, '') < ?
        ORDER BY start_ts ASC, event_id ASC
        """,
        (week_start, week_end),
    ).fetchall()


def _collect_notable_messages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT m.message_id, m.subject, m.from_addr, m.sent_at, ml.label, ml.score
        FROM messages AS m
        JOIN message_labels AS ml ON ml.message_id = m.message_id
        WHERE ml.label IN ('advisor-request', 'lab', 'ta')
        ORDER BY ml.score DESC, COALESCE(m.sent_at, ''), m.message_id ASC, ml.label ASC
        """
    ).fetchall()


def _collect_watchlist_changes(conn: sqlite3.Connection, diff_start: str, diff_end: str) -> dict[str, list[sqlite3.Row]]:
    conn.row_factory = sqlite3.Row
    promoted_rows = conn.execute(
        """
        SELECT ep.source_message_id, ep.title, ep.confidence, mw.watch_kind, mw.seen_count
        FROM event_proposals AS ep
        JOIN message_watchlist AS mw ON mw.source_message_id = ep.source_message_id
        WHERE COALESCE(ep.created_at, '') >= ? AND COALESCE(ep.created_at, '') < ?
          AND ep.status NOT IN ('rejected')
        ORDER BY ep.confidence DESC, ep.source_message_id ASC
        """,
        (diff_start, diff_end),
    ).fetchall()
    promoted_ids = {str(row["source_message_id"]) for row in promoted_rows}
    new_rows = [
        row
        for row in conn.execute(
            """
            SELECT source_message_id, title, watch_kind, promotion_score, seen_count
            FROM message_watchlist
            WHERE COALESCE(first_seen_at, '') >= ? AND COALESCE(first_seen_at, '') < ?
            ORDER BY promotion_score DESC, source_message_id ASC
            """,
            (diff_start, diff_end),
        ).fetchall()
        if str(row["source_message_id"]) not in promoted_ids
    ]
    resurfaced_rows = [
        row
        for row in conn.execute(
            """
            SELECT source_message_id, title, watch_kind, promotion_score, seen_count
            FROM message_watchlist
            WHERE COALESCE(last_seen_at, '') >= ? AND COALESCE(last_seen_at, '') < ? AND seen_count >= 2
            ORDER BY promotion_score DESC, source_message_id ASC
            """,
            (diff_start, diff_end),
        ).fetchall()
        if str(row["source_message_id"]) not in promoted_ids
    ]
    return {
        "new": list(new_rows),
        "resurfaced": list(resurfaced_rows),
        "promoted": list(promoted_rows),
    }


def generate_weekly_review(config: PipelineConfig, *, as_of: datetime | None = None) -> dict:
    bootstrap_workspace(config)
    review_moment = _normalize_as_of(as_of)
    diff_start = review_moment - timedelta(days=7)
    week_end = review_moment + timedelta(days=7)
    artifact_dir = config.workspace_root / "data" / "digests"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"weekly-review-{review_moment.strftime('%Y%m%d')}.md"

    with sqlite3.connect(config.database_path) as conn:
        label_counts = _collect_label_counts(conn)
        unresolved_proposals = _collect_unresolved_proposals(conn)
        calendar_events = _collect_calendar_events(conn, review_moment.isoformat(), week_end.isoformat())
        notable_messages = _collect_notable_messages(conn)
        watchlist_changes = _collect_watchlist_changes(conn, diff_start.isoformat(), review_moment.isoformat())

    lines = [
        f"# Weekly Review — {review_moment.date().isoformat()}",
        "",
        f"Review window: {review_moment.isoformat()} to {week_end.isoformat()}",
        "",
        "## Message label summary",
    ]
    if label_counts:
        lines.extend(f"- {label}: {count}" for label, count in label_counts)
    else:
        lines.append("- No classified messages available.")

    lines.extend(["", "## Unresolved proposals"])
    if unresolved_proposals:
        for proposal in unresolved_proposals:
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
        lines.append("- No unresolved proposals.")

    lines.extend(["", "## Calendar events this week"])
    if calendar_events:
        for event in calendar_events:
            lines.append(
                "- {start_ts} — {summary} ({status}){location}".format(
                    start_ts=event["start_ts"] or "n/a",
                    summary=event["summary"] or "Untitled event",
                    status=event["status"] or "unknown",
                    location=f" @ {event['location']}" if event["location"] else "",
                )
            )
    else:
        lines.append("- No calendar events found in the upcoming week.")

    lines.extend(["", "## Notable advisor / lab / TA items"])
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
        lines.append("- No notable advisor/lab/TA items.")

    lines.extend([
        "",
        "## Watchlist changes",
        f"- new watchlist entries: {len(watchlist_changes['new'])}",
        f"- resurfaced watchlist entries: {len(watchlist_changes['resurfaced'])}",
        f"- promoted from watchlist: {len(watchlist_changes['promoted'])}",
    ])
    if watchlist_changes["new"]:
        lines.extend(
            f"  - NEW `{row['source_message_id']}` [{row['watch_kind']}] {row['title']} — score={float(row['promotion_score']):.2f}, seen_count={int(row['seen_count'])}"
            for row in watchlist_changes["new"][:5]
        )
    if watchlist_changes["resurfaced"]:
        lines.extend(
            f"  - RESURFACED `{row['source_message_id']}` [{row['watch_kind']}] {row['title']} — score={float(row['promotion_score']):.2f}, seen_count={int(row['seen_count'])}"
            for row in watchlist_changes["resurfaced"][:5]
        )
    if watchlist_changes["promoted"]:
        lines.extend(
            f"  - PROMOTED `{row['source_message_id']}` [{row['watch_kind']}] {row['title']} — confidence={float(row['confidence']):.2f}, seen_count={int(row['seen_count'])}"
            for row in watchlist_changes["promoted"][:5]
        )

    artifact_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    checkpoints = {}
    if config.checkpoints_path.exists():
        checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8"))
    checkpoints.setdefault("weekly_review", {})
    checkpoints["weekly_review"]["latest"] = {
        "review_date": review_moment.date().isoformat(),
        "artifact_file": artifact_path.name,
        "unresolved_proposal_count": len(unresolved_proposals),
        "calendar_event_count": len(calendar_events),
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "artifact_path": artifact_path,
        "review_date": review_moment.date().isoformat(),
        "label_count": len(label_counts),
        "unresolved_proposal_count": len(unresolved_proposals),
        "calendar_event_count": len(calendar_events),
        "notable_item_count": len(notable_messages),
    }
