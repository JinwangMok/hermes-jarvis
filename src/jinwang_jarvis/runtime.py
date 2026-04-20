from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .bootstrap import bootstrap_workspace
from .calendar import collect_calendar_snapshots
from .classifier import classify_messages
from .config import PipelineConfig
from .digest import generate_digest
from .mail import collect_mail_snapshots
from .knowledge import synthesize_knowledge
from .proposals import generate_proposals
from .review import generate_weekly_review


CYCLE_SERVICE_NAME = "jinwang-jarvis-cycle.service"
CYCLE_TIMER_NAME = "jinwang-jarvis-cycle.timer"
WEEKLY_SERVICE_NAME = "jinwang-jarvis-weekly-review.service"
WEEKLY_TIMER_NAME = "jinwang-jarvis-weekly-review.timer"
DEFAULT_POLL_MINUTES = 5


def run_pipeline_cycle(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    mail_result = collect_mail_snapshots(config)
    calendar_result = collect_calendar_snapshots(config)
    classification_result = classify_messages(config)
    proposal_result = generate_proposals(config)
    knowledge_result = synthesize_knowledge(config, write_wiki=False)
    digest_result = generate_digest(config, proposal_result)
    return {
        "mail": mail_result,
        "calendar": calendar_result,
        "classification": classification_result,
        "proposals": proposal_result,
        "knowledge": knowledge_result,
        "digest": digest_result,
    }


def run_weekly_review_cycle(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    return generate_weekly_review(config)


def _python_exec() -> str:
    return "python3"


def build_systemd_unit_texts(config: PipelineConfig, *, poll_minutes: int = DEFAULT_POLL_MINUTES) -> dict[str, str]:
    workspace = config.workspace_root
    command_prefix = f"cd {workspace} && PYTHONPATH=src {_python_exec()} -m jinwang_jarvis.cli"
    service_path = os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    cycle_service = f"""[Unit]
Description=Jinwang Jarvis pipeline polling cycle
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={workspace}
Environment=PATH={service_path}
ExecStart=/bin/bash -lc '{command_prefix} run-cycle --config config/pipeline.yaml'
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
ExecStart=/bin/bash -lc '{command_prefix} weekly-review --config config/pipeline.yaml'
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
