from pathlib import Path

from jinwang_jarvis.config import load_pipeline_config


def test_load_pipeline_config_exposes_reproducible_workspace_metadata():
    config_path = Path("config/pipeline.yaml")

    config = load_pipeline_config(config_path)

    assert config.project_name == "jinwang-jarvis"
    assert config.workspace_root == Path("/home/jinwang/workspace/jinwang-jarvis")
    assert config.database_path == Path("/home/jinwang/workspace/jinwang-jarvis/state/personal_intel.db")
    assert config.sender_map_path == Path("/home/jinwang/wiki/raw/articles/netai-members-contact-information-sanitized-2026-04-19.md")
    assert config.mail_snapshot_dir == Path("/home/jinwang/workspace/jinwang-jarvis/data/snapshots/mail")
    assert config.calendar_snapshot_dir == Path("/home/jinwang/workspace/jinwang-jarvis/data/snapshots/calendar")
    assert config.calendar_id == "primary"
    assert config.calendar_max_results == 50
    assert config.calendar_time_min == "2026-04-19T00:00:00+09:00"
    assert config.calendar_time_max == "2026-05-19T00:00:00+09:00"
    assert config.hermes_integration_mode == "boundary-cli"
