from pathlib import Path

import json

from jinwang_jarvis.cli import main


def _config_text(root: Path) -> str:
    return """
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
classification:
  sender_map_path: {sender_map}
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
""".format(root=root.as_posix(), sender_map=(root / 'sender-map.md').as_posix())


def test_cli_bootstrap_command_initializes_workspace(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    exit_code = main(["bootstrap", "--config", str(config_file)])

    assert exit_code == 0
    assert (tmp_path / "state" / "personal_intel.db").exists()
    assert (tmp_path / "data" / "snapshots" / "mail").is_dir()


def test_cli_collect_mail_command_runs_collection(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    exit_code = main(["collect-mail", "--config", str(config_file), "--runner", "fake"])

    assert exit_code == 0
    assert list((tmp_path / "data" / "snapshots" / "mail").glob("*.jsonl"))
    assert (tmp_path / "state" / "checkpoints.json").exists()


def test_cli_collect_calendar_command_runs_collection(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    exit_code = main(["collect-calendar", "--config", str(config_file), "--runner", "fake"])

    assert exit_code == 0
    assert list((tmp_path / "data" / "snapshots" / "calendar").glob("*.jsonl"))
    assert (tmp_path / "state" / "checkpoints.json").exists()


def test_cli_classify_messages_command_runs_pipeline(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    main(["bootstrap", "--config", str(config_file)])

    import sqlite3
    with sqlite3.connect(tmp_path / "state" / "personal_intel.db") as conn:
        conn.execute("INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?)", ("m1", "smartx", "inbox", "meeting request", "jongwon@smartx.kr", "2026-04-19T00:00:00+00:00", 0))
        conn.commit()

    exit_code = main(["classify-messages", "--config", str(config_file)])

    assert exit_code == 0


def test_cli_run_cycle_and_install_systemd_commands(tmp_path: Path, monkeypatch):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    cycle_exit_code = main(["run-cycle", "--config", str(config_file)])
    assert cycle_exit_code == 0

    calls = []

    def fake_run(cmd, check=True):
        calls.append(cmd)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr("jinwang_jarvis.runtime.subprocess.run", fake_run)
    install_exit_code = main(["install-systemd", "--config", str(config_file), "--poll-minutes", "10", "--no-enable"])
    assert install_exit_code == 0
    assert calls == [["systemctl", "--user", "daemon-reload"]]
    assert (tmp_path / "systemd" / "jinwang-jarvis-cycle.timer").exists()


def test_cli_generate_proposals_and_record_feedback_commands_run_pipeline(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n- Ph.D. Student | 목진왕(JinWang Mok) | jinwang@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    main(["bootstrap", "--config", str(config_file)])

    import sqlite3
    with sqlite3.connect(tmp_path / "state" / "personal_intel.db") as conn:
        conn.execute("INSERT INTO sender_identities (email, display_name, role, organization, priority_base, source_note) VALUES (?, ?, ?, ?, ?, ?)", ("jongwon@smartx.kr", "김종원", "advisor", "smartx", 100, "test"))
        conn.execute("INSERT INTO sender_identities (email, display_name, role, organization, priority_base, source_note) VALUES (?, ?, ?, ?, ?, ?)", ("jinwang@smartx.kr", "목진왕", "self", "smartx", 90, "test"))
        conn.execute("INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("m1", "smartx", "inbox", "Please review meeting agenda 2027-04-21 13:00", "jongwon@smartx.kr", "2026-04-19T00:00:00+00:00", "2026-04-19T00:00:00+00:00", 0))
        conn.execute("INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)", ("m1", "advisor-request", 100.0, "{}"))
        conn.execute("INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)", ("m1", "meeting", 40.0, "{}"))
        conn.commit()

    exit_code = main(["generate-proposals", "--config", str(config_file)])
    assert exit_code == 0
    proposal_files = list((tmp_path / "data" / "proposals").glob("proposal-run-*.json"))
    digest_files = list((tmp_path / "data" / "digests").glob("digest-*.md"))
    assert proposal_files
    assert digest_files

    with sqlite3.connect(tmp_path / "state" / "personal_intel.db") as conn:
        proposal_id = conn.execute("SELECT proposal_id FROM event_proposals LIMIT 1").fetchone()[0]

    feedback_exit_code = main([
        "record-feedback",
        "--config",
        str(config_file),
        "--proposal-id",
        proposal_id,
        "--decision",
        "reject",
        "--reason-code",
        "duplicate",
        "--note",
        "Already handled",
    ])
    assert feedback_exit_code == 0
    assert list((tmp_path / "data" / "feedback").glob("feedback-*.json"))
    assert list((tmp_path / "data" / "briefings").glob("briefing-*.json"))


def test_cli_weekly_review_and_backfill_commands_write_artifacts(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    main(["bootstrap", "--config", str(config_file)])

    import sqlite3
    with sqlite3.connect(tmp_path / "state" / "personal_intel.db") as conn:
        conn.execute("INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("m1", "smartx", "inbox", "Meeting agenda", "jongwon@smartx.kr", "2026-04-20T00:00:00+00:00", "2026-04-20T00:00:00+00:00", 0))
        conn.execute("INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)", ("m1", "advisor-request", 100.0, "{}"))
        conn.execute("INSERT INTO calendar_events (event_id, calendar_id, summary, status, start_ts, end_ts, location, html_link, dedup_key, raw_json_path, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("evt-1", "primary", "Weekly lab meeting", "confirmed", "2026-04-23T09:00:00+00:00", "2026-04-23T10:00:00+00:00", "Lab", None, "weekly lab meeting|2026-04-23t09:00:00+00:00", None, "2026-04-20T00:00:00+00:00"))
        conn.commit()

    review_exit_code = main(["weekly-review", "--config", str(config_file)])
    backfill_exit_code = main(["backfill", "--config", str(config_file), "--windows", "1w,1m"])

    assert review_exit_code == 0
    assert backfill_exit_code == 0
    assert list((tmp_path / "data" / "digests").glob("weekly-review-*.md"))
    assert list((tmp_path / "data" / "exports").glob("backfill-*.json"))


def test_cli_synthesize_knowledge_command_writes_watchlist_artifact(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    (tmp_path / "wiki" / "queries").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "comparisons").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "raw" / "transcripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "SCHEMA.md").write_text("# Wiki Schema\n", encoding="utf-8")
    (tmp_path / "wiki" / "index.md").write_text("# Wiki Index\n\n> Last updated: 2026-04-19 | Total pages: 0\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n", encoding="utf-8")
    (tmp_path / "wiki" / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")

    main(["bootstrap", "--config", str(config_file)])
    proposal_dir = tmp_path / "data" / "proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    proposal_artifact = proposal_dir / "proposal-run-20260419T174030Z.json"
    proposal_artifact.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-19T17:40:30Z",
                "proposal_count": 0,
                "proposals": [],
                "suppressed": [
                    {
                        "source_message_id": "m-watch",
                        "title": "Re: update",
                        "reason": {"kind": "low-confidence"},
                        "details": {
                            "scores": {
                                "priority": 0.6,
                                "action": 0.4,
                                "calendar": 0.2,
                                "noise": 0.0,
                                "date_confidence": 0.22,
                                "signal_confidence": 0.95
                            },
                            "message": {
                                "account": "smartx",
                                "folder_kind": "inbox",
                                "role": "advisor",
                                "from_addr": "jongwon@smartx.kr"
                            },
                            "labels": ["advisor-fyi", "work-account"],
                            "subject_hints": ["work-account"],
                            "parse": {"matched_date": None, "matched_time": None},
                            "suppression": {"kind": "low-confidence"}
                        }
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (tmp_path / "state" / "checkpoints.json").write_text(
        json.dumps({"proposals": {"latest": {"artifact_file": proposal_artifact.name, "generated_at": "2026-04-19T17:40:30Z"}}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    exit_code = main(["synthesize-knowledge", "--config", str(config_file)])

    assert exit_code == 0
    assert list((tmp_path / "data" / "watchlists").glob("watchlist-*.json"))


def test_cli_generate_briefing_command_writes_artifact(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")
    main(["bootstrap", "--config", str(config_file)])

    import sqlite3
    with sqlite3.connect(tmp_path / "state" / "personal_intel.db") as conn:
        conn.execute("INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, sent_at, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("m1", "smartx", "inbox", "Meeting agenda", "jongwon@smartx.kr", "2026-04-20T00:00:00+00:00", "2026-04-20T00:00:00+00:00", 0))
        conn.execute("INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)", ("m1", "advisor-request", 100.0, "{}"))
        conn.execute("INSERT INTO event_proposals (proposal_id, source_message_id, title, start_ts, end_ts, location, description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("p1", "m1", "Meeting agenda", "2026-04-22T10:00:00+09:00", "2026-04-22T11:00:00+09:00", "Zoom", "Discuss work", 0.9, "proposed", "meeting-agenda", "{}", "2026-04-20T00:00:00+00:00", None))
        conn.commit()

    exit_code = main(["generate-briefing", "--config", str(config_file)])
    assert exit_code == 0
    assert list((tmp_path / "data" / "briefings").glob("briefing-*.json"))


def test_cli_record_feedback_allow_create_calendar_command(monkeypatch, tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")
    main(["bootstrap", "--config", str(config_file)])

    import sqlite3
    with sqlite3.connect(tmp_path / "state" / "personal_intel.db") as conn:
        conn.execute("INSERT INTO event_proposals (proposal_id, source_message_id, title, start_ts, end_ts, location, description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("p-cal", "m-cal", "Calendar me", "2026-04-22T10:00:00+09:00", "2026-04-22T11:00:00+09:00", "Zoom", "Discuss work", 0.9, "proposed", "calendar-me", "{}", "2026-04-20T00:00:00+00:00", None))
        conn.commit()

    monkeypatch.setattr("jinwang_jarvis.feedback._default_runner", lambda args: json.dumps({"status": "created", "id": "evt-1"}))

    exit_code = main(["record-feedback", "--config", str(config_file), "--proposal-id", "p-cal", "--decision", "allow", "--reason-code", "other", "--create-calendar"])
    assert exit_code == 0
    feedback_files = list((tmp_path / "data" / "feedback").glob("feedback-*.json"))
    assert feedback_files
    payload = json.loads(feedback_files[0].read_text(encoding="utf-8"))
    assert payload["calendar_result"]["id"] == "evt-1"


def test_cli_backfill_next_command_runs_incremental_extension(monkeypatch, tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")
    main(["bootstrap", "--config", str(config_file)])
    (tmp_path / "state" / "checkpoints.json").write_text(json.dumps({"backfill": {"6m": {"status": "completed"}}}), encoding="utf-8")

    folder_listing = "| NAME | DESC |\n|------|------|\n| INBOX | \\HasNoChildren |\n| [Gmail]/보낸편지함 | \\HasNoChildren, \\Sent |\n"

    def fake_runner(args):
        if args[:3] == ["himalaya", "folder", "list"]:
            return folder_listing
        if args[:3] == ["himalaya", "envelope", "list"]:
            return json.dumps([])
        raise AssertionError(args)

    monkeypatch.setattr("jinwang_jarvis.backfill._default_runner", fake_runner)

    exit_code = main(["backfill-next", "--config", str(config_file), "--max-months", "36"])
    assert exit_code == 0
    assert list((tmp_path / "data" / "exports").glob("backfill-9m-*.json"))
