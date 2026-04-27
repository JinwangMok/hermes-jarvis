import json
import sqlite3
from pathlib import Path

from jinwang_jarvis.bootstrap import bootstrap_workspace
from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.knowledge import synthesize_knowledge


SENDER_MAP = """
## Current members
- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr
"""


def _config_text(root: Path) -> str:
    return """
workspace_root: {root}
wiki_root: {wiki}
accounts:
  - personal
  - smartx
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 50
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
""".format(root=root.as_posix(), wiki=(root / "wiki").as_posix(), sender_map=(root / "sender-map.md").as_posix())


def _init_wiki(root: Path) -> None:
    wiki = root / "wiki"
    (wiki / "queries").mkdir(parents=True, exist_ok=True)
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "concepts").mkdir(parents=True, exist_ok=True)
    (wiki / "comparisons").mkdir(parents=True, exist_ok=True)
    (wiki / "raw" / "transcripts").mkdir(parents=True, exist_ok=True)
    (wiki / "SCHEMA.md").write_text("# Wiki Schema\n", encoding="utf-8")
    (wiki / "index.md").write_text("# Wiki Index\n\n> Last updated: 2026-04-19 | Total pages: 0\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")


def _load_config(tmp_path: Path):
    (tmp_path / "sender-map.md").write_text(SENDER_MAP, encoding="utf-8")
    _init_wiki(tmp_path)
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")
    return load_pipeline_config(config_file)


def test_synthesize_knowledge_creates_watchlist_artifact_and_wiki_summary(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    proposal_dir = config.workspace_root / "data" / "proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    proposal_artifact = proposal_dir / "proposal-run-20260419T174030Z.json"
    proposal_artifact.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-19T17:40:30Z",
                "proposal_count": 1,
                "proposals": [
                    {
                        "source_message_id": "p1",
                        "title": "Active proposal",
                        "start_ts": "2026-04-20T10:00:00+09:00",
                    }
                ],
                "suppressed": [
                    {
                        "source_message_id": "m-watch",
                        "title": "Fwd: [ITRC 인재양성대전 2026] 사전등록자 조사 요청 (~3/30까지)",
                        "reason": {"kind": "low-confidence"},
                        "details": {
                            "scores": {
                                "priority": 0.56,
                                "action": 0.36,
                                "calendar": 0.31,
                                "noise": 0.02,
                                "date_confidence": 0.62,
                                "signal_confidence": 0.0,
                            },
                            "message": {
                                "account": "smartx",
                                "folder_kind": "inbox",
                                "role": "lab-member",
                                "from_addr": "member@gist.ac.kr",
                            },
                            "labels": ["lab", "work-account"],
                            "subject_hints": ["work-account"],
                            "parse": {"matched_date": "3/30", "matched_time": None},
                            "suppression": {"kind": "low-confidence"},
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config.checkpoints_path.write_text(
        json.dumps({"proposals": {"latest": {"artifact_file": proposal_artifact.name, "generated_at": "2026-04-19T17:40:30Z"}}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO messages (
                message_id, account, folder_kind, thread_key, subject, from_addr, to_addrs, cc_addrs,
                self_role, interaction_role, sent_at, snippet, body_path, raw_json_path, is_seen, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "smartx:SENT:self-shared-1",
                "smartx",
                "sent",
                None,
                "[NetCS Announce][Agentic AI] The 2nd OmOCon Seoul 참석 수기 공유",
                "jinwang@smartx.kr",
                '["info@smartx.kr"]',
                "[]",
                "sent-by-me",
                "broadcast",
                "2026-04-20T18:30:00+09:00",
                "OmOCon 참석 수기를 SmartX 정보 채널에 공유함",
                None,
                None,
                1,
                "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.commit()

    result = synthesize_knowledge(config, write_wiki=True)

    assert result["watchlist_count"] == 1
    assert result["artifact_path"].exists()
    assert result["wiki_page_path"].exists()
    assert result["memory_note_paths"]["index"].exists()
    assert result["memory_note_paths"]["recent_important"].exists()
    assert result["memory_note_paths"]["sent_mail_memory"].exists()
    sent_memory_text = result["memory_note_paths"]["sent_mail_memory"].read_text(encoding="utf-8")
    assert "# 내가 보낸 메일 기억" in sent_memory_text
    assert "shared-context" in sent_memory_text
    assert "smartx:SENT:self-shared-1" in sent_memory_text
    assert "OmOCon 참석 수기를 SmartX 정보 채널에 공유함" in sent_memory_text

    payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert payload["watchlist"][0]["source_message_id"] == "m-watch"
    assert payload["watchlist"][0]["watch_kind"] == "promotion-candidate"

    with sqlite3.connect(config.database_path) as conn:
        row = conn.execute(
            "SELECT source_message_id, seen_count FROM message_watchlist WHERE source_message_id = ?",
            ("m-watch",),
        ).fetchone()
    assert row == ("m-watch", 1)

    wiki_text = result["wiki_page_path"].read_text(encoding="utf-8")
    assert "m-watch" in wiki_text
    assert "promotion candidates" in wiki_text.casefold()
    assert "generated: true" in wiki_text
    assert "generator: jinwang-jarvis" in wiki_text
    assert "authority: derived" in wiki_text
    assert f"operational_source_of_truth: {config.database_path}" in wiki_text
    assert result["wiki_governance"]["generated_report_contract"].endswith("generated-report-contract.md")

    index_text = (config.wiki_root / "index.md").read_text(encoding="utf-8")
    assert "jinwang-jarvis-importance-shift-watchlist" in index_text


def test_synthesize_knowledge_skips_feedback_and_past_event_suppressed_items(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    proposal_dir = config.workspace_root / "data" / "proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    proposal_artifact = proposal_dir / "proposal-run-20260426T120000Z.json"
    suppressed_items = []
    for idx, suppression_kind in enumerate(["feedback-dedup-key", "feedback-summary-match", "policy-past-event"], start=1):
        suppressed_items.append(
            {
                "source_message_id": f"m-skip-{idx}",
                "title": "Already resolved event",
                "reason": {"kind": "low-confidence"},
                "details": {
                    "scores": {
                        "priority": 0.99,
                        "action": 0.42,
                        "calendar": 0.26,
                        "noise": 0.02,
                        "date_confidence": 0.62,
                        "signal_confidence": 0.0,
                    },
                    "message": {"account": "smartx", "folder_kind": "inbox", "role": "self", "from_addr": "jinwangmok@gm.gist.ac.kr"},
                    "labels": ["work-account"],
                    "subject_hints": ["work-account", "explicit-date-or-time"],
                    "parse": {"matched_date": "2026-04-25", "matched_time": None},
                    "suppression": {"kind": suppression_kind},
                },
            }
        )
    proposal_artifact.write_text(
        json.dumps(
            {"generated_at": "2026-04-26T12:00:00Z", "proposal_count": 0, "proposals": [], "suppressed": suppressed_items},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config.checkpoints_path.write_text(
        json.dumps({"proposals": {"latest": {"artifact_file": proposal_artifact.name, "generated_at": "2026-04-26T12:00:00Z"}}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = synthesize_knowledge(config, write_wiki=True)

    assert result["watchlist_count"] == 0
    payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert payload["watchlist"] == []
    wiki_text = result["wiki_page_path"].read_text(encoding="utf-8")
    assert "No current promotion candidates" in wiki_text
    with sqlite3.connect(config.database_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM message_watchlist WHERE source_message_id LIKE 'm-skip-%'").fetchone()[0]
    assert count == 0


def test_synthesize_knowledge_updates_seen_count_for_existing_watch_item(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    proposal_dir = config.workspace_root / "data" / "proposals"
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
                                "signal_confidence": 0.95,
                            },
                            "message": {
                                "account": "smartx",
                                "folder_kind": "inbox",
                                "role": "advisor",
                                "from_addr": "jongwon@smartx.kr",
                            },
                            "labels": ["advisor-fyi", "work-account"],
                            "subject_hints": ["work-account"],
                            "parse": {"matched_date": None, "matched_time": None},
                            "suppression": {"kind": "low-confidence"},
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    config.checkpoints_path.write_text(
        json.dumps({"proposals": {"latest": {"artifact_file": proposal_artifact.name, "generated_at": "2026-04-19T17:40:30Z"}}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    synthesize_knowledge(config, write_wiki=False)
    synthesize_knowledge(config, write_wiki=False)

    with sqlite3.connect(config.database_path) as conn:
        row = conn.execute(
            "SELECT seen_count FROM message_watchlist WHERE source_message_id = ?",
            ("m-watch",),
        ).fetchone()

    assert row == (2,)