from pathlib import Path

from jinwang_jarvis.runtime import build_hermes_standby_unit_texts, build_systemd_unit_texts, check_hermes_jarvis_health
from jinwang_jarvis.config import load_pipeline_config


def _write_runtime_config(tmp_path: Path) -> Path:
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
    return config_file


def _write_hermes_health_files(hermes_home: Path, *, gateway_log: str) -> None:
    (hermes_home / "logs").mkdir(parents=True)
    (hermes_home / "cron").mkdir(parents=True)
    (hermes_home / "logs" / "gateway.log").write_text(gateway_log, encoding="utf-8")
    (hermes_home / "cron" / "jobs.json").write_text(
        '{"jobs":[{"id":"daily","enabled":true,"next_run_at":"2999-01-01T00:00:00+00:00"}]}',
        encoding="utf-8",
    )


def _fake_systemctl(calls: list[list[str]], *, on_restart=None):
    def fake_run(cmd, check=False, text=True, capture_output=True):
        calls.append(cmd)
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        result = Result()
        if cmd[:2] != ["systemctl", "--user"]:
            return result
        action = cmd[2]
        if action == "is-active":
            result.stdout = "active"
        elif action == "is-enabled":
            result.stdout = "enabled"
        elif action == "show":
            result.stdout = "ActiveState=active\nSubState=running\nMainPID=123\nExecMainStatus=0"
        elif action == "restart" and on_restart:
            on_restart()
        return result

    return fake_run


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


def test_build_hermes_standby_unit_texts_contains_restart_and_health_alert_contract(tmp_path: Path, monkeypatch):
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

    monkeypatch.setenv("PATH", "/x/bin:/x/bin:/usr/bin")
    config = load_pipeline_config(config_file)
    units = build_hermes_standby_unit_texts(config, health_minutes=5, stale_minutes=15)

    assert units["hermes-gateway.service"].count("/x/bin") == 1
    assert "Restart=always" in units["hermes-gateway.service"]
    assert "StartLimitBurst=10" in units["hermes-gateway.service"]
    assert "EnvironmentFile=-" in units["jinwang-jarvis-hermes-health.service"]
    assert ".hermes/.env" in units["jinwang-jarvis-hermes-health.service"]
    assert "JARVIS_HEALTH_DISCORD_CHANNEL=1496014213276241922" in units["jinwang-jarvis-hermes-health.service"]
    assert "hermes-health-check" in units["jinwang-jarvis-hermes-health.service"]
    assert "--discord-alert --restart" in units["jinwang-jarvis-hermes-health.service"]
    assert "--readiness-timeout-seconds 45" in units["jinwang-jarvis-hermes-health.service"]
    assert "OnUnitActiveSec=5min" in units["jinwang-jarvis-hermes-health.timer"]
    assert "Persistent=true" in units["jinwang-jarvis-hermes-health.timer"]


def test_hermes_health_check_requires_discord_ready_gateway_log(tmp_path: Path, monkeypatch):
    config = load_pipeline_config(_write_runtime_config(tmp_path))
    hermes_home = tmp_path / ".hermes"
    _write_hermes_health_files(
        hermes_home,
        gateway_log="""
2026-04-30 13:52:04,945 INFO gateway.run: Stopping gateway for restart...
2026-04-30 13:52:04,958 INFO gateway.platforms.discord: [Discord] Disconnected
2026-04-30 13:52:05,089 INFO gateway.run: Gateway stopped
""",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    calls: list[list[str]] = []
    monkeypatch.setattr("jinwang_jarvis.runtime.subprocess.run", _fake_systemctl(calls))

    result = check_hermes_jarvis_health(
        config,
        readiness_timeout_seconds=0,
        discord_api_check=False,
    )

    assert result["status"] == "alert"
    assert any("not Discord-ready" in issue for issue in result["issues"])
    assert result["checks"]["gateway_log"]["ready"] is False


def test_hermes_health_check_passes_when_gateway_log_is_discord_ready(tmp_path: Path, monkeypatch):
    config = load_pipeline_config(_write_runtime_config(tmp_path))
    hermes_home = tmp_path / ".hermes"
    _write_hermes_health_files(
        hermes_home,
        gateway_log="""
2026-04-30 13:52:24,778 INFO gateway.run: Connecting to discord...
2026-04-30 13:52:28,942 INFO gateway.platforms.discord: [Discord] Connected as BoramaeBot#9049
2026-04-30 13:52:28,951 INFO gateway.run: ✓ discord connected
2026-04-30 13:52:28,953 INFO gateway.run: Gateway running with 1 platform(s)
""",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    calls: list[list[str]] = []
    monkeypatch.setattr("jinwang_jarvis.runtime.subprocess.run", _fake_systemctl(calls))

    result = check_hermes_jarvis_health(
        config,
        readiness_timeout_seconds=0,
        discord_api_check=False,
    )

    assert result["status"] == "ok"
    assert result["issues"] == []
    assert result["checks"]["gateway_log"]["ready"] is True


def test_hermes_health_check_restarts_active_but_not_ready_gateway(tmp_path: Path, monkeypatch):
    config = load_pipeline_config(_write_runtime_config(tmp_path))
    hermes_home = tmp_path / ".hermes"
    gateway_log = hermes_home / "logs" / "gateway.log"
    _write_hermes_health_files(
        hermes_home,
        gateway_log="""
2026-04-30 13:52:04,945 INFO gateway.run: Stopping gateway for restart...
2026-04-30 13:52:05,089 INFO gateway.run: Gateway stopped
""",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    calls: list[list[str]] = []

    def mark_ready_after_restart():
        gateway_log.write_text(
            """
2026-04-30 13:53:00,001 INFO gateway.run: Starting Hermes Gateway...
2026-04-30 13:53:02,100 INFO gateway.platforms.discord: [Discord] Connected as BoramaeBot#9049
2026-04-30 13:53:02,101 INFO gateway.run: ✓ discord connected
2026-04-30 13:53:02,102 INFO gateway.run: Gateway running with 1 platform(s)
""",
            encoding="utf-8",
        )

    monkeypatch.setattr("jinwang_jarvis.runtime.subprocess.run", _fake_systemctl(calls, on_restart=mark_ready_after_restart))

    result = check_hermes_jarvis_health(
        config,
        restart=True,
        readiness_timeout_seconds=0,
        discord_api_check=False,
    )

    assert result["status"] == "ok"
    assert result["actions"] == ["restarted hermes-gateway.service"]
    assert ["systemctl", "--user", "restart", "hermes-gateway.service"] in calls
