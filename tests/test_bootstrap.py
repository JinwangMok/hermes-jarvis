import sqlite3
from pathlib import Path

from jinwang_jarvis.bootstrap import REQUIRED_DIRECTORIES, bootstrap_workspace
from jinwang_jarvis.config import load_pipeline_config


def test_bootstrap_workspace_creates_required_directories_and_tables(tmp_path: Path):
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
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
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
""".format(root=tmp_path.as_posix()),
        encoding="utf-8",
    )
    config = load_pipeline_config(config_file)

    bootstrap_workspace(config)

    for relative_dir in REQUIRED_DIRECTORIES:
        assert (tmp_path / relative_dir).is_dir(), relative_dir

    assert config.database_path.exists()
    with sqlite3.connect(config.database_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {"messages", "sender_identities", "message_labels", "action_signals", "calendar_events", "event_proposals", "proposal_feedback", "backfill_runs"} <= table_names
