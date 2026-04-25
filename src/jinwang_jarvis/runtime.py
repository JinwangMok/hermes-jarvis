from __future__ import annotations

import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

from .bootstrap import bootstrap_workspace
from .briefing import generate_briefing
from .calendar import collect_calendar_snapshots
from .classifier import classify_messages
from .config import PipelineConfig
from .digest import generate_digest
from .intelligence import generate_daily_intelligence_report
from .mail import collect_mail_snapshots
from .knowledge import synthesize_knowledge
from .proposals import generate_proposals
from .review import generate_weekly_review
from .watch import run_watch_cycle as run_external_watch_cycle


CYCLE_SERVICE_NAME = "jinwang-jarvis-cycle.service"
CYCLE_TIMER_NAME = "jinwang-jarvis-cycle.timer"
WEEKLY_SERVICE_NAME = "jinwang-jarvis-weekly-review.service"
WEEKLY_TIMER_NAME = "jinwang-jarvis-weekly-review.timer"
HERMES_GATEWAY_SERVICE_NAME = "hermes-gateway.service"
HERMES_HEALTH_SERVICE_NAME = "jinwang-jarvis-hermes-health.service"
HERMES_HEALTH_TIMER_NAME = "jinwang-jarvis-hermes-health.timer"
DEFAULT_POLL_MINUTES = 5
DEFAULT_HEALTH_MINUTES = 5
DEFAULT_STALE_MINUTES = 15


def _config_arg(config: PipelineConfig) -> str:
    try:
        return str(config.config_path.relative_to(config.workspace_root))
    except ValueError:
        return str(config.config_path)


def run_pipeline_cycle(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    mail_result = collect_mail_snapshots(config)
    calendar_result = collect_calendar_snapshots(config)
    classification_result = classify_messages(config)
    proposal_result = generate_proposals(config)
    knowledge_result = synthesize_knowledge(config, write_wiki=False)
    digest_result = generate_digest(config, proposal_result)
    intelligence_result = generate_daily_intelligence_report(config)
    briefing_result = generate_briefing(config)
    return {
        "mail": mail_result,
        "calendar": calendar_result,
        "classification": classification_result,
        "proposals": proposal_result,
        "knowledge": knowledge_result,
        "digest": digest_result,
        "intelligence": intelligence_result,
        "briefing": briefing_result,
    }


def run_watch_cycle(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    return run_external_watch_cycle(config)


def run_weekly_review_cycle(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    return generate_weekly_review(config)


def _python_exec() -> str:
    return "python3"


def build_systemd_unit_texts(config: PipelineConfig, *, poll_minutes: int = DEFAULT_POLL_MINUTES) -> dict[str, str]:
    workspace = config.workspace_root
    command_prefix = f"cd {workspace} && PYTHONPATH=src {_python_exec()} -m jinwang_jarvis.cli"
    config_arg = _config_arg(config)
    service_path = os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    cycle_service = f"""[Unit]
Description=Jinwang Jarvis pipeline polling cycle
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={workspace}
Environment=PATH={service_path}
ExecStart=/bin/bash -lc '{command_prefix} run-cycle --config {config_arg}'
"""
    cycle_timer = f"""[Unit]
Description=Run Jinwang Jarvis pipeline every {poll_minutes} minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec={poll_minutes}min
Persistent=true
Unit={CYCLE_SERVICE_NAME}

[Install]
WantedBy=timers.target
"""
    weekly_service = f"""[Unit]
Description=Jinwang Jarvis weekly review
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={workspace}
Environment=PATH={service_path}
ExecStart=/bin/bash -lc '{command_prefix} weekly-review --config {config_arg}'
"""
    weekly_timer = """[Unit]
Description=Run Jinwang Jarvis weekly review on Sunday evening

[Timer]
OnCalendar=Sun *-*-* 20:00:00
Persistent=true
Unit=jinwang-jarvis-weekly-review.service

[Install]
WantedBy=timers.target
"""
    return {
        CYCLE_SERVICE_NAME: cycle_service,
        CYCLE_TIMER_NAME: cycle_timer,
        WEEKLY_SERVICE_NAME: weekly_service,
        WEEKLY_TIMER_NAME: weekly_timer,
    }


def _discord_channel_from_config(config: PipelineConfig, fallback: str = "") -> str:
    deliver_channel = config.deliver_channel or ""
    if deliver_channel.startswith("discord:"):
        return deliver_channel.split(":", 1)[1]
    if deliver_channel.isdigit():
        return deliver_channel
    return fallback


def build_hermes_standby_unit_texts(
    config: PipelineConfig,
    *,
    health_minutes: int = DEFAULT_HEALTH_MINUTES,
    discord_channel: str = "",
    stale_minutes: int = DEFAULT_STALE_MINUTES,
) -> dict[str, str]:
    """Render repo-managed user units for Hermes+Jarvis always-on standby.

    Hermes cron jobs run inside the gateway process, so the Jarvis 24/7
    contract is anchored on a resilient Hermes gateway service plus an
    independent health timer that can alert Discord when that chain breaks.
    """
    workspace = config.workspace_root
    config_arg = _config_arg(config)
    service_path = os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    channel = discord_channel or _discord_channel_from_config(config)
    quoted_workspace = shlex.quote(str(workspace))
    quoted_config_arg = shlex.quote(config_arg)
    python_exec = shlex.quote(_python_exec())
    home = Path.home()
    health_command = (
        f"cd {quoted_workspace} && PYTHONPATH=src {python_exec} -m jinwang_jarvis.cli "
        f"hermes-health-check --config {quoted_config_arg} --discord-alert --restart "
        f"--stale-minutes {int(stale_minutes)}"
    )

    gateway_service = f"""[Unit]
Description=Hermes Agent Gateway - Messaging Platform Integration
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=600
StartLimitBurst=10

[Service]
Type=simple
WorkingDirectory={home}/.hermes/hermes-agent
Environment=PATH={home}/.hermes/hermes-agent/venv/bin:{home}/.hermes/hermes-agent/node_modules/.bin:{service_path}
Environment=VIRTUAL_ENV={home}/.hermes/hermes-agent/venv
Environment=HERMES_HOME={home}/.hermes
ExecStart={home}/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run --replace
Restart=always
RestartSec=30
RestartForceExitStatus=75
KillMode=mixed
KillSignal=SIGTERM
ExecReload=/bin/kill -USR1 $MAINPID
TimeoutStopSec=180
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    health_service = f"""[Unit]
Description=Check Hermes gateway + Jarvis cron health and alert Discord
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={workspace}
Environment=PATH={service_path}
Environment=HERMES_HOME={home}/.hermes
Environment=JARVIS_HEALTH_DISCORD_CHANNEL={channel}
EnvironmentFile=-{home}/.hermes/.env
ExecStart=/bin/bash -lc '{health_command}'
"""
    health_timer = f"""[Unit]
Description=Run Hermes/Jarvis health check every {health_minutes} minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec={health_minutes}min
Persistent=true
Unit={HERMES_HEALTH_SERVICE_NAME}

[Install]
WantedBy=timers.target
"""
    return {
        HERMES_GATEWAY_SERVICE_NAME: gateway_service,
        HERMES_HEALTH_SERVICE_NAME: health_service,
        HERMES_HEALTH_TIMER_NAME: health_timer,
    }


def _run_systemctl(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(["systemctl", "--user", *args], check=False, text=True, capture_output=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except Exception:
        return None


def _load_hermes_cron_jobs(hermes_home: Path) -> list[dict]:
    jobs_file = hermes_home / "cron" / "jobs.json"
    if not jobs_file.exists():
        return []
    data = json.loads(jobs_file.read_text(encoding="utf-8"))
    return list(data.get("jobs", []))


def send_discord_bot_message(message: str, *, channel_id: str = "", bot_token: str = "") -> dict:
    channel_id = channel_id or os.environ.get("JARVIS_HEALTH_DISCORD_CHANNEL", "") or os.environ.get("DISCORD_HOME_CHANNEL", "")
    bot_token = bot_token or os.environ.get("DISCORD_BOT_TOKEN", "")
    if not channel_id or not bot_token:
        return {"sent": False, "reason": "missing DISCORD_BOT_TOKEN or channel"}

    payload = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=payload,
        headers={
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "jinwang-jarvis-health-check/0.1",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            return {"sent": True, "status": response.status, "channel_id": channel_id}
    except HTTPError as exc:
        return {"sent": False, "status": exc.code, "reason": exc.reason}
    except URLError as exc:
        return {"sent": False, "reason": str(exc.reason)}


def check_hermes_jarvis_health(
    config: PipelineConfig,
    *,
    stale_minutes: int = DEFAULT_STALE_MINUTES,
    restart: bool = False,
    discord_alert: bool = False,
    discord_channel: str = "",
) -> dict:
    hermes_home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    now = datetime.now(timezone.utc)
    issues: list[str] = []
    actions: list[str] = []

    active_rc, active_state, active_err = _run_systemctl(["is-active", HERMES_GATEWAY_SERVICE_NAME])
    enabled_rc, enabled_state, enabled_err = _run_systemctl(["is-enabled", HERMES_GATEWAY_SERVICE_NAME])
    if active_rc != 0 or active_state != "active":
        issues.append(f"{HERMES_GATEWAY_SERVICE_NAME} is not active: {active_state or active_err or active_rc}")
    if enabled_rc != 0 or enabled_state != "enabled":
        issues.append(f"{HERMES_GATEWAY_SERVICE_NAME} is not enabled: {enabled_state or enabled_err or enabled_rc}")

    jobs = _load_hermes_cron_jobs(hermes_home)
    enabled_jobs = [job for job in jobs if job.get("enabled", True) and job.get("state") != "paused"]
    if not enabled_jobs:
        issues.append(f"No enabled Hermes cron jobs found under {hermes_home / 'cron' / 'jobs.json'}")
    stale_seconds = int(stale_minutes) * 60
    stale_jobs: list[str] = []
    for job in enabled_jobs:
        next_run = job.get("next_run_at")
        if not next_run:
            continue
        next_dt = _parse_iso_datetime(str(next_run))
        if next_dt and (now - next_dt).total_seconds() > stale_seconds:
            stale_jobs.append(f"{job.get('name', job.get('id'))} next_run_at={next_run}")
    if stale_jobs:
        issues.append("Hermes cron appears stale: " + "; ".join(stale_jobs[:5]))

    if restart and any(HERMES_GATEWAY_SERVICE_NAME in issue for issue in issues):
        restart_rc, restart_out, restart_err = _run_systemctl(["restart", HERMES_GATEWAY_SERVICE_NAME])
        if restart_rc == 0:
            actions.append(f"restarted {HERMES_GATEWAY_SERVICE_NAME}")
        else:
            issues.append(f"restart failed: {restart_err or restart_out or restart_rc}")

    status = "ok" if not issues else "alert"
    result = {
        "status": status,
        "checked_at": now.isoformat(),
        "hermes_home": str(hermes_home),
        "gateway_active": active_state,
        "gateway_enabled": enabled_state,
        "enabled_cron_jobs": len(enabled_jobs),
        "issues": issues,
        "actions": actions,
    }

    if discord_alert and issues:
        channel = discord_channel or _discord_channel_from_config(config)
        message = "🚨 Jinwang Jarvis health alert\n" + "\n".join(f"- {issue}" for issue in issues)
        if actions:
            message += "\nActions:\n" + "\n".join(f"- {action}" for action in actions)
        result["discord"] = send_discord_bot_message(message, channel_id=channel)
    return result


def install_hermes_standby_units(
    config: PipelineConfig,
    *,
    health_minutes: int = DEFAULT_HEALTH_MINUTES,
    discord_channel: str = "",
    stale_minutes: int = DEFAULT_STALE_MINUTES,
    enable: bool = True,
    install_gateway: bool = False,
    workspace_only: bool = False,
) -> dict:
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    workspace_unit_dir = config.workspace_root / "systemd"
    workspace_unit_dir.mkdir(parents=True, exist_ok=True)
    units = build_hermes_standby_unit_texts(
        config,
        health_minutes=health_minutes,
        discord_channel=discord_channel,
        stale_minutes=stale_minutes,
    )
    workspace_paths: dict[str, str] = {}
    installed_paths: dict[str, str] = {}
    for name, content in units.items():
        workspace_path = workspace_unit_dir / name
        workspace_path.write_text(content, encoding="utf-8")
        workspace_paths[name] = str(workspace_path)
        if not workspace_only and (name != HERMES_GATEWAY_SERVICE_NAME or install_gateway):
            unit_dir.mkdir(parents=True, exist_ok=True)
            user_path = unit_dir / name
            user_path.write_text(content, encoding="utf-8")
            installed_paths[name] = str(user_path)

    if installed_paths:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        if enable:
            subprocess.run(["systemctl", "--user", "enable", "--now", HERMES_HEALTH_TIMER_NAME], check=True)
            if install_gateway:
                subprocess.run(["systemctl", "--user", "enable", HERMES_GATEWAY_SERVICE_NAME], check=True)

    return {
        "workspace_unit_dir": str(workspace_unit_dir),
        "installed_unit_dir": str(unit_dir),
        "workspace_units": workspace_paths,
        "installed_units": installed_paths,
        "health_minutes": health_minutes,
        "stale_minutes": stale_minutes,
        "enabled": enable,
        "install_gateway": install_gateway,
        "workspace_only": workspace_only,
    }


def install_systemd_user_units(config: PipelineConfig, *, poll_minutes: int = DEFAULT_POLL_MINUTES, enable: bool = True) -> dict:
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    workspace_unit_dir = config.workspace_root / "systemd"
    workspace_unit_dir.mkdir(parents=True, exist_ok=True)
    units = build_systemd_unit_texts(config, poll_minutes=poll_minutes)
    written_paths: dict[str, str] = {}
    for name, content in units.items():
        user_path = unit_dir / name
        workspace_path = workspace_unit_dir / name
        user_path.write_text(content, encoding="utf-8")
        workspace_path.write_text(content, encoding="utf-8")
        written_paths[name] = str(user_path)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    if enable:
        subprocess.run(["systemctl", "--user", "enable", "--now", CYCLE_TIMER_NAME, WEEKLY_TIMER_NAME], check=True)

    return {
        "unit_dir": str(unit_dir),
        "workspace_unit_dir": str(workspace_unit_dir),
        "poll_minutes": poll_minutes,
        "enabled": enable,
        "units": written_paths,
    }
