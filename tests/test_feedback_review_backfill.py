import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from jinwang_jarvis.backfill import run_progressive_backfill
from jinwang_jarvis.bootstrap import bootstrap_workspace
from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.feedback import record_proposal_feedback
from jinwang_jarvis.review import generate_weekly_review


def _write_config(root: Path) -> Path:
    config_file = root / "pipeline.yaml"
    config_file.write_text(
        """
workspace_root: {root}
wiki_root: /home/jinwang/wiki
accounts:
  - personal
  - smartx
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 100
  sent_folder_overrides: {{}}
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
  max_results: 5
  time_min: 2026-04-19T00:00:00+09:00
  time_max: 2026-05-19T00:00:00+09:00
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord-origin
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: jinwang-jarvis
""".format(root=root.as_posix()),
        encoding="utf-8",
    )
    return config_file


def test_record_proposal_feedback_persists_decision_and_artifact(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            """
            INSERT INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location,
                description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p-1",
                "m-1",
                "Advisor meeting",
                "2026-04-22T09:00:00+00:00",
                "2026-04-22T09:30:00+00:00",
                "Zoom",
                "Meet with advisor",
                0.95,
                "proposed",
                "advisor-meeting",
                json.dumps({"source": "test"}),
                "2026-04-20T00:00:00+00:00",
                None,
            ),
        )
        conn.commit()

    result = record_proposal_feedback(
        config,
        "p-1",
        "reject",
        "already-scheduled",
        "Already on calendar.",
        recorded_at=datetime(2026, 4, 21, 0, 0, tzinfo=UTC),
    )

    assert result["updated_status"] == "rejected"
    with sqlite3.connect(config.database_path) as conn:
        feedback_row = conn.execute(
            "SELECT decision, reason_code, freeform_note, recorded_at FROM proposal_feedback WHERE proposal_id = ?",
            ("p-1",),
        ).fetchone()
        proposal_row = conn.execute(
            "SELECT status, resolved_at FROM event_proposals WHERE proposal_id = ?",
            ("p-1",),
        ).fetchone()

    assert feedback_row == (
        "reject",
        "already-scheduled",
        "Already on calendar.",
        "2026-04-21T00:00:00+00:00",
    )
    assert proposal_row == ("rejected", "2026-04-21T00:00:00+00:00")

    artifact = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact["proposal_id"] == "p-1"
    assert artifact["decision"] == "reject"
    assert artifact["updated_status"] == "rejected"
    assert artifact["proposal"]["title"] == "Advisor meeting"


def test_generate_weekly_review_writes_markdown_summary(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            "INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-advisor", "smartx", "inbox", "Meeting agenda", "jongwon@smartx.kr", "2026-04-20T09:00:00+00:00", "2026-04-20T09:01:00+00:00", 0),
        )
        conn.execute(
            "INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-ta", "smartx", "inbox", "[TA] Lab section", "ta@example.org", "2026-04-20T10:00:00+00:00", "2026-04-20T10:01:00+00:00", 0),
        )
        conn.execute(
            "INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)",
            ("m-advisor", "advisor-request", 100.0, json.dumps({"matched": "advisor"})),
        )
        conn.execute(
            "INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)",
            ("m-ta", "ta", 35.0, json.dumps({"matched": "ta"})),
        )
        conn.execute(
            """
            INSERT INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location,
                description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p-open",
                "m-advisor",
                "Prepare advisor meeting",
                "2026-04-24T10:00:00+00:00",
                "2026-04-24T10:30:00+00:00",
                "Room 101",
                "Discuss progress",
                0.9,
                "proposed",
                "p-open",
                json.dumps({"source": "advisor"}),
                "2026-04-20T00:00:00+00:00",
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO calendar_events (
                event_id, calendar_id, summary, status, start_ts, end_ts, location,
                html_link, dedup_key, raw_json_path, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evt-1",
                "primary",
                "Weekly lab meeting",
                "confirmed",
                "2026-04-23T09:00:00+00:00",
                "2026-04-23T10:00:00+00:00",
                "Lab",
                None,
                "evt-1",
                None,
                "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO message_watchlist (
                source_message_id, title, watch_kind, promotion_score, first_seen_at,
                last_seen_at, seen_count, latest_reason_json, latest_artifact_file, wiki_note_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "m-watch-new",
                "Suppressed but rising",
                "promotion-candidate",
                0.63,
                "2026-04-18T00:00:00+00:00",
                "2026-04-20T00:00:00+00:00",
                1,
                json.dumps({"reason": {"kind": "low-confidence"}}),
                "watchlist-new.json",
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO message_watchlist (
                source_message_id, title, watch_kind, promotion_score, first_seen_at,
                last_seen_at, seen_count, latest_reason_json, latest_artifact_file, wiki_note_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "m-watch-old",
                "Resurfaced item",
                "advisor-fyi-revival",
                0.71,
                "2026-04-10T00:00:00+00:00",
                "2026-04-20T00:00:00+00:00",
                3,
                json.dumps({"reason": {"kind": "low-confidence"}}),
                "watchlist-old.json",
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO message_watchlist (
                source_message_id, title, watch_kind, promotion_score, first_seen_at,
                last_seen_at, seen_count, latest_reason_json, latest_artifact_file, wiki_note_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "m-advisor",
                "Prepare advisor meeting",
                "reply-backed-candidate",
                0.88,
                "2026-04-15T00:00:00+00:00",
                "2026-04-20T00:00:00+00:00",
                2,
                json.dumps({"reason": {"kind": "low-confidence"}}),
                "watchlist-promoted.json",
                None,
            ),
        )
        conn.commit()

    result = generate_weekly_review(config, as_of=datetime(2026, 4, 21, 0, 0, tzinfo=UTC))

    content = result["artifact_path"].read_text(encoding="utf-8")
    assert "# Weekly Review — 2026-04-21" in content
    assert "- advisor-request: 1" in content
    assert "Prepare advisor meeting (`p-open`)" in content
    assert "Weekly lab meeting (confirmed) @ Lab" in content
    assert "[advisor-request] Meeting agenda" in content
    assert "[ta] [TA] Lab section" in content
    assert "## Watchlist changes" in content
    assert "new watchlist entries: 1" in content
    assert "resurfaced watchlist entries: 1" in content
    assert "promoted from watchlist: 1" in content


def test_run_progressive_backfill_records_windows_and_artifacts(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)

    folder_listing = "| NAME | DESC |\n|------|------|\n| INBOX | \\HasNoChildren |\n| [Gmail]/보낸편지함 | \\HasNoChildren, \\Sent |\n"
    pages = {
        ("personal", "inbox", 1): [
            {"id": "p-inbox-1", "flags": [], "subject": "Recent personal", "from": {"name": None, "addr": "a@example.org"}, "to": {"name": None, "addr": "jinwangmok@gmail.com"}, "date": "2026-04-19 00:00+00:00", "has_attachment": False},
            {"id": "p-inbox-2", "flags": [], "subject": "Mid personal", "from": {"name": None, "addr": "b@example.org"}, "to": {"name": None, "addr": "jinwangmok@gmail.com"}, "date": "2026-03-25 00:00+00:00", "has_attachment": False},
            {"id": "p-inbox-3", "flags": [], "subject": "Old personal", "from": {"name": None, "addr": "c@example.org"}, "to": {"name": None, "addr": "jinwangmok@gmail.com"}, "date": "2025-12-01 00:00+00:00", "has_attachment": False},
        ],
        ("personal", "sent", 1): [
            {"id": "p-sent-1", "flags": ["Seen"], "subject": "Re: Recent personal", "from": {"name": None, "addr": "jinwangmok@gmail.com"}, "to": {"name": None, "addr": "a@example.org"}, "date": "2026-04-18 00:00+00:00", "has_attachment": False},
        ],
        ("smartx", "inbox", 1): [
            {"id": "s-inbox-1", "flags": [], "subject": "Recent smartx", "from": {"name": None, "addr": "d@example.org"}, "to": {"name": None, "addr": "jinwang@smartx.kr"}, "date": "2026-04-17 00:00+00:00", "has_attachment": False},
            {"id": "s-inbox-2", "flags": [], "subject": "Month smartx", "from": {"name": None, "addr": "e@example.org"}, "to": {"name": None, "addr": "jinwang@smartx.kr"}, "date": "2026-03-28 00:00+00:00", "has_attachment": False},
            {"id": "s-inbox-3", "flags": [], "subject": "Too old smartx", "from": {"name": None, "addr": "f@example.org"}, "to": {"name": None, "addr": "jinwang@smartx.kr"}, "date": "2025-10-10 00:00+00:00", "has_attachment": False},
        ],
        ("smartx", "sent", 1): [
            {"id": "s-sent-1", "flags": ["Seen"], "subject": "Re: Recent smartx", "from": {"name": None, "addr": "jinwang@smartx.kr"}, "to": {"name": None, "addr": "d@example.org"}, "date": "2026-04-16 00:00+00:00", "has_attachment": False},
        ],
    }

    def runner(args):
        if args[:3] == ["himalaya", "folder", "list"]:
            return folder_listing
        if args[:3] == ["himalaya", "envelope", "list"]:
            account = args[4]
            page = int(args[args.index("--page") + 1])
            folder_kind = "sent" if "--folder" in args else "inbox"
            payload = pages.get((account, folder_kind, page), [])
            return json.dumps(payload, ensure_ascii=False)
        raise AssertionError(args)

    result = run_progressive_backfill(
        config,
        as_of=datetime(2026, 4, 21, 0, 0, tzinfo=UTC),
        windows=("1w", "1m"),
        runner=runner,
    )

    assert [run["window_name"] for run in result["runs"]] == ["1w", "1m"]
    with sqlite3.connect(config.database_path) as conn:
        rows = conn.execute(
            "SELECT window_name, status, messages_scanned FROM backfill_runs ORDER BY CASE window_name WHEN '1w' THEN 1 WHEN '1m' THEN 2 END"
        ).fetchall()
        message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert rows == [
        ("1w", "completed", 4),
        ("1m", "completed", 6),
    ]
    assert message_count == 6

    checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8"))
    assert checkpoints["backfill"]["1m"]["messages_scanned"] == 6
    assert checkpoints["backfill"]["1m"]["source_mode"] == "himalaya-pagination"
    artifact_files = sorted((tmp_path / "data" / "exports").glob("backfill-*.json"))
    assert len(artifact_files) == 2
    artifact_1m = next(path for path in artifact_files if "backfill-1m-" in path.name)
    artifact_payload = json.loads(artifact_1m.read_text(encoding="utf-8"))
    assert artifact_payload["status"] == "completed"
    assert artifact_payload["accounts"]["smartx"]["inbox_count"] == 2
