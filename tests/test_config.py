from pathlib import Path

from zeus_os.config import load_pipeline_config


def test_load_pipeline_config_exposes_reproducible_workspace_metadata():
    config_path = Path("config/pipeline.yaml")

    config = load_pipeline_config(config_path)

    assert config.project_name == "zeus-os"
    assert config.workspace_root == Path("/home/jinwang/workspace/zeus-os")
    assert config.wiki_root == Path("/home/jinwang/workspace/zeus-os/wiki")
    assert config.database_path == Path("/home/jinwang/workspace/zeus-os/state/personal_intel.db")
    assert config.sender_map_path == Path("/home/jinwang/workspace/zeus-os/config/sender-map.example.md")
    assert config.mail_snapshot_dir == Path("/home/jinwang/workspace/zeus-os/data/snapshots/mail")
    assert config.calendar_snapshot_dir == Path("/home/jinwang/workspace/zeus-os/data/snapshots/calendar")
    assert config.calendar_id == "primary"
    assert config.calendar_max_results == 50
    assert config.self_addresses == ("you@example.com",)
    assert config.work_accounts == ("work",)
    assert config.hermes_integration_mode == "boundary-cli"
    assert config.watch.default_poll_minutes == 60
    assert config.watch.source_config_dir == Path("/home/jinwang/workspace/zeus-os/config/watch-sources")
    assert config.watch.adjudicator_model == "gpt-5.4"
