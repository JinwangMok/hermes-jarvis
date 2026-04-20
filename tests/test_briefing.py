import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from jinwang_jarvis.bootstrap import bootstrap_workspace
from jinwang_jarvis.briefing import generate_briefing
from jinwang_jarvis.config import load_pipeline_config


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
  deliver_channel: discord:1493529569926578276
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: jinwang-jarvis
""".format(root=root.as_posix()),
        encoding="utf-8",
    )
    return config_file


def test_generate_briefing_writes_natural_language_sections_and_target(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            "INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-continue", "smartx", "inbox", "Budget planning", "advisor@smartx.kr", "2026-03-10T00:00:00+00:00", "2026-04-20T00:00:00+00:00", 0),
        )
        conn.execute(
            "INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-new", "smartx", "inbox", "New meeting request", "colleague@smartx.kr", "2026-04-18T00:00:00+00:00", "2026-04-20T00:00:00+00:00", 0),
        )
        conn.execute(
            "INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)",
            ("m-continue", "advisor-request", 90.0, "{}"),
        )
        conn.execute(
            "INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)",
            ("m-new", "meeting", 50.0, "{}"),
        )
        conn.execute(
            "INSERT INTO message_watchlist (source_message_id, title, watch_kind, promotion_score, first_seen_at, last_seen_at, seen_count, latest_reason_json, latest_artifact_file, wiki_note_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-continue", "Budget planning", "promotion-candidate", 0.7, "2026-03-10T00:00:00+00:00", "2026-04-20T00:00:00+00:00", 3, json.dumps({"reason": {"kind": "reply-backed"}}), "watch.json", None),
        )
        conn.execute(
            """
            INSERT INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location,
                description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p-continue",
                "m-continue",
                "Budget planning",
                None,
                None,
                None,
                "Long-running budget work",
                0.81,
                "proposed",
                "budget-planning",
                json.dumps({"source": "test"}),
                "2026-04-20T00:00:00+00:00",
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location,
                description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p-new",
                "m-new",
                "New meeting request",
                "2026-04-22T10:00:00+09:00",
                "2026-04-22T11:00:00+09:00",
                "Zoom",
                "Quick sync",
                0.92,
                "proposed",
                "new-meeting-request",
                json.dumps({"source": "test"}),
                "2026-04-20T00:00:00+00:00",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO backfill_runs (window_name, window_start, window_end, status, messages_scanned, notes) VALUES (?, ?, ?, ?, ?, ?)",
            ("6m", "2025-10-20T00:00:00+00:00", "2026-04-20T00:00:00+00:00", "completed", 100, "done"),
        )
        conn.commit()

    result = generate_briefing(config, as_of=datetime(2026, 4, 20, 0, 0, tzinfo=UTC))

    artifact = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    text = artifact["message_text"]
    assert artifact["target_channel"] == "discord:1493529569926578276"
    assert "## 최근 중요한 일" in text
    assert "## 계속 중요한 일" in text
    assert "## 새로 중요해진 일" in text
    assert "## 추천 일정" in text
    assert "캘린더에 등록할까요?" in text
    assert "discord:1493529569926578276" in text
    assert "[p-new]" not in text
    assert "허용 후보: New meeting request" in text
    assert artifact["pending_approval_count"] == 1
    assert artifact["sections"]["schedule_recommendations"][0]["proposal_id"] == "p-new"


def test_generate_briefing_uses_today_to_hide_past_deadlines_and_old_recent_items(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            "INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-fresh", "smartx", "inbox", "GIST 서버 접근 안내 요청", "advisor@smartx.kr", "2026-04-16T05:23:00+00:00", "2026-04-20T00:00:00+00:00", 0),
        )
        conn.execute(
            "INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-old", "smartx", "inbox", "오래된 검토 요청", "advisor@smartx.kr", "2026-03-17T14:44:00+00:00", "2026-04-20T00:00:00+00:00", 0),
        )
        conn.execute(
            "INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("m-past-deadline", "smartx", "inbox", "발표자료 제출 안내 (17일 오후 4시까지)", "advisor@smartx.kr", "2026-03-17T08:23:00+00:00", "2026-04-20T00:00:00+00:00", 0),
        )
        for message_id in ("m-fresh", "m-old", "m-past-deadline"):
            conn.execute(
                "INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)",
                (message_id, "advisor-request", 90.0, "{}"),
            )
        conn.execute(
            """
            INSERT INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location,
                description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p-fresh",
                "m-fresh",
                "GIST 서버 접근 안내 요청",
                None,
                None,
                None,
                "fresh",
                0.91,
                "proposed",
                "fresh",
                json.dumps({"source": "test"}),
                "2026-04-20T00:00:00+00:00",
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location,
                description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p-old",
                "m-old",
                "오래된 검토 요청",
                None,
                None,
                None,
                "old",
                0.95,
                "proposed",
                "old",
                json.dumps({"source": "test"}),
                "2026-04-20T00:00:00+00:00",
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location,
                description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "p-past-deadline",
                "m-past-deadline",
                "발표자료 제출 안내",
                None,
                None,
                None,
                "past deadline",
                0.99,
                "proposed",
                "past-deadline",
                json.dumps({"source": "test"}),
                "2026-04-20T00:00:00+00:00",
                None,
            ),
        )
        conn.commit()

    result = generate_briefing(config, as_of=datetime(2026, 4, 20, 0, 0, tzinfo=UTC))

    artifact = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    recent_ids = [item["proposal_id"] for item in artifact["sections"]["recent_important"]]
    continuing_ids = [item["proposal_id"] for item in artifact["sections"]["continuing_important"]]
    new_ids = [item["proposal_id"] for item in artifact["sections"]["newly_important"]]

    assert recent_ids == ["p-fresh"]
    assert "p-old" in continuing_ids
    assert "p-past-deadline" not in recent_ids
    assert "p-past-deadline" not in continuing_ids
    assert "p-past-deadline" not in new_ids
