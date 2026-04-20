import json
import sqlite3
from pathlib import Path

from jinwang_jarvis.classifier import classify_messages
from jinwang_jarvis.config import load_pipeline_config


SENDER_MAP = """
## Current members
- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr
- Ph.D. Student | 목진왕(JinWang Mok) | jinwang@smartx.kr / jinwangmok@gmail.com
"""


def test_classify_messages_loads_sender_identities_and_labels(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(
        """
workspace_root: {root}
wiki_root: /home/jinwang/wiki
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
  self_addresses:
    - jinwangmok@gmail.com
  work_accounts:
    - smartx
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
""".format(root=tmp_path.as_posix(), sender_map=(tmp_path / 'sender-map.md').as_posix()),
        encoding="utf-8",
    )
    (tmp_path / "sender-map.md").write_text(SENDER_MAP, encoding="utf-8")
    config = load_pipeline_config(config_file)

    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.database_path) as conn:
        conn.execute("CREATE TABLE messages (message_id TEXT PRIMARY KEY, account TEXT, folder_kind TEXT, thread_key TEXT, subject TEXT, from_addr TEXT, to_addrs TEXT, cc_addrs TEXT, sent_at TEXT, snippet TEXT, body_path TEXT, raw_json_path TEXT, is_seen INTEGER, ingested_at TEXT)")
        conn.execute("CREATE TABLE sender_identities (email TEXT PRIMARY KEY, display_name TEXT, role TEXT NOT NULL, organization TEXT, priority_base INTEGER DEFAULT 0, source_note TEXT)")
        conn.execute("CREATE TABLE message_labels (message_id TEXT NOT NULL, label TEXT NOT NULL, score REAL NOT NULL, reason_json TEXT, PRIMARY KEY (message_id, label))")
        conn.execute("INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?)", ("m1", "smartx", "inbox", "Please review E2E meeting agenda", "jongwon@smartx.kr", "2026-04-19T00:00:00+00:00", 0))
        conn.execute("INSERT INTO messages (message_id, account, folder_kind, subject, from_addr, ingested_at, is_seen) VALUES (?, ?, ?, ?, ?, ?, ?)", ("m2", "personal", "inbox", "Security alert for jinwang@smartx.kr", "no-reply@accounts.google.com", "2026-04-19T00:00:00+00:00", 0))
        conn.commit()

    result = classify_messages(config)

    assert result["message_count"] == 2
    assert result["identity_count"] >= 2

    with sqlite3.connect(config.database_path) as conn:
        identities = dict(conn.execute("SELECT email, role FROM sender_identities"))
        labels = conn.execute("SELECT message_id, label FROM message_labels ORDER BY message_id, label").fetchall()

    assert identities["jongwon@smartx.kr"] == "advisor"
    assert identities["jinwangmok@gmail.com"] == "self"
    assert ("m1", "advisor-request") in labels
    assert ("m1", "meeting") in labels
    assert ("m2", "security-routine") in labels
