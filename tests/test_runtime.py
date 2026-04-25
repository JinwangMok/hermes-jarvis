from pathlib import Path

from jinwang_jarvis.runtime import build_hermes_standby_unit_texts, build_systemd_unit_texts
from jinwang_jarvis.config import load_pipeline_config


def test_build_systemd_unit_texts_contains_persistent_polling_contract(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(
        """
workspace_root: {root}
wiki_root: /home/jinwang/wiki
accounts:
  - personal
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
""".format(root=tmp_path.as_posix(), sender_map=(tmp_path / 'sender-map.md').as_posix()),
        encoding="utf-8",
    )

    config = load_pipeline_config(config_file)
    units = build_systemd_unit_texts(config, poll_minutes=15)

    assert "Persistent=true" in units["jinwang-jarvis-cycle.timer"]
    assert "OnUnitActiveSec=15min" in units["jinwang-jarvis-cycle.timer"]
    assert "run-cycle --config pipeline.yaml" in units["jinwang-jarvis-cycle.service"]
    assert "Environment=PATH=" in units["jinwang-jarvis-cycle.service"]
    assert "OnCalendar=Sun *-*-* 20:00:00" in units["jinwang-jarvis-weekly-review.timer"]


def test_build_hermes_standby_unit_texts_contains_restart_and_health_alert_contract(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    (tmp_path / "sender-map.md").write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file.write_text(
        """
workspace_root: {root}
wiki_root: /home/jinwang/wiki
accounts:
  - personal
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 100
  sent_folder_overrides: {{}}
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
  max_results: 5
classification:
  sender_map_path: {sender_map}
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord:1496014213276241922
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: jinwang-jarvis
""".format(root=tmp_path.as_posix(), sender_map=(tmp_path / 'sender-map.md').as_posix()),
        encoding="utf-8",
    )

    config = load_pipeline_config(config_file)
    units = build_hermes_standby_unit_texts(config, health_minutes=5, stale_minutes=15)

    assert "Restart=always" in units["hermes-gateway.service"]
    assert "StartLimitBurst=10" in units["hermes-gateway.service"]
    assert "EnvironmentFile=-" in units["jinwang-jarvis-hermes-health.service"]
    assert ".hermes/.env" in units["jinwang-jarvis-hermes-health.service"]
    assert "JARVIS_HEALTH_DISCORD_CHANNEL=1496014213276241922" in units["jinwang-jarvis-hermes-health.service"]
    assert "hermes-health-check" in units["jinwang-jarvis-hermes-health.service"]
    assert "--discord-alert --restart" in units["jinwang-jarvis-hermes-health.service"]
    assert "OnUnitActiveSec=5min" in units["jinwang-jarvis-hermes-health.timer"]
    assert "Persistent=true" in units["jinwang-jarvis-hermes-health.timer"]
