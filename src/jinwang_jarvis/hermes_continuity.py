from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

import yaml


DEFAULT_HERMES_HOME = Path.home() / ".hermes"
DEFAULT_HERMES_AGENT_DIR = DEFAULT_HERMES_HOME / "hermes-agent"
DEFAULT_VOXCPM_HEALTH_URL = "http://10.40.40.40:9100/health"


@dataclass(frozen=True)
class HermesCapability:
    name: str
    description: str
    required_skill: str | None = None
    required_external_dir_hint: str | None = None
    health_url: str | None = None


CAPABILITIES: tuple[HermesCapability, ...] = (
    HermesCapability(
        name="styled_voice",
        description="Jarvis-hosted styled-voice skill backed by VoxCPM, without Hermes source patches",
        required_skill="styled-voice",
        required_external_dir_hint="styled-voice",
        health_url=DEFAULT_VOXCPM_HEALTH_URL,
    ),
    HermesCapability(
        name="discord_voice_stt_enhance",
        description="Discord voice/STT enhancement runtime is available as a Hermes external skill",
        required_skill="discord-voice-stt-enhance",
        required_external_dir_hint="discord-voice-stt-enhance",
    ),
    HermesCapability(
        name="restart_warning_report_contract",
        description="User-commanded Hermes update/restart warns Discord before restart and reports changes after active",
    ),
)


def _status(ok: bool, detail: str = "", **extra: object) -> dict:
    return {"ok": ok, "detail": detail, **extra}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _external_dirs_from_config(config_path: Path) -> list[str]:
    raw = _load_yaml(config_path)
    skills = raw.get("skills") or {}
    dirs = skills.get("external_dirs") or []
    if isinstance(dirs, str):
        return [dirs]
    return [str(item) for item in dirs if item]


def _run_python_probe(hermes_agent_dir: Path, code: str, timeout: int = 20) -> tuple[bool, str]:
    python = hermes_agent_dir / "venv" / "bin" / "python"
    if not python.exists():
        python = hermes_agent_dir / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path("python3")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(hermes_agent_dir)
    proc = subprocess.run(
        [str(python), "-c", code],
        cwd=str(hermes_agent_dir),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output.strip()


def _http_health(url: str, timeout: int = 5) -> dict:
    try:
        with request.urlopen(url, timeout=timeout) as response:
            body = response.read(4096)
            return _status(response.status < 400, f"HTTP {response.status}", body_bytes=len(body))
    except HTTPError as exc:
        return _status(False, f"HTTP {exc.code}: {exc.reason}")
    except URLError as exc:
        return _status(False, str(exc.reason))
    except Exception as exc:
        return _status(False, str(exc))


def check_hermes_customizations(
    *,
    hermes_home: Path | str = DEFAULT_HERMES_HOME,
    hermes_agent_dir: Path | str = DEFAULT_HERMES_AGENT_DIR,
    hermes_config_path: Path | str | None = None,
    include_network: bool = False,
) -> dict:
    """Inspect the two-component Hermes+Jarvis customization contract.

    This is intentionally passive: no file writes, no restart, no patch apply.
    Secrets from Hermes config are never returned; only presence/paths/statuses.
    """
    hermes_home = Path(hermes_home).expanduser()
    hermes_agent_dir = Path(hermes_agent_dir).expanduser()
    hermes_config_path = Path(hermes_config_path).expanduser() if hermes_config_path else hermes_home / "config.yaml"

    external_dirs = _external_dirs_from_config(hermes_config_path)
    checks: dict[str, dict] = {
        "hermes_agent_dir": _status(hermes_agent_dir.exists(), str(hermes_agent_dir)),
        "hermes_config": _status(hermes_config_path.exists(), str(hermes_config_path)),
        "external_dirs": _status(bool(external_dirs), f"{len(external_dirs)} configured", dirs=external_dirs),
    }

    skill_probe_ok, skill_probe_output = _run_python_probe(
        hermes_agent_dir,
        "import json; from agent.skill_commands import scan_skill_commands; "
        "cmds=scan_skill_commands(); print(json.dumps(sorted(cmds.keys())))",
    )
    skill_commands: list[str] = []
    if skill_probe_ok:
        try:
            skill_commands = json.loads(skill_probe_output)
        except Exception:
            skill_probe_ok = False
    checks["skill_scan"] = _status(skill_probe_ok, "Hermes skill scanner", commands=skill_commands if skill_probe_ok else [], error="" if skill_probe_ok else "probe failed; stderr redacted")

    discord_probe_ok, discord_probe_output = _run_python_probe(
        hermes_agent_dir,
        "import json; from hermes_cli.commands import discord_skill_commands_by_category; "
        "cats, unc, hidden = discord_skill_commands_by_category(set()); "
        "flat=[x[2] for xs in cats.values() for x in xs] + [x[2] for x in unc]; "
        "print(json.dumps({'commands': sorted(flat), 'hidden': hidden}))",
    )
    discord_commands: list[str] = []
    discord_hidden = None
    if discord_probe_ok:
        try:
            parsed = json.loads(discord_probe_output)
            discord_commands = list(parsed.get("commands") or [])
            discord_hidden = parsed.get("hidden")
        except Exception:
            discord_probe_ok = False
    checks["discord_skill_exposure"] = _status(discord_probe_ok, "Discord /skill command exposure", commands=discord_commands if discord_probe_ok else [], hidden=discord_hidden, error="" if discord_probe_ok else "probe failed; stderr redacted")

    capabilities: dict[str, dict] = {}
    for capability in CAPABILITIES:
        c_checks: dict[str, dict] = {}
        if capability.required_external_dir_hint:
            matching_dirs = [d for d in external_dirs if capability.required_external_dir_hint in d]
            c_checks["external_dir"] = _status(
                bool(matching_dirs) or f"/{capability.required_skill}" in skill_commands,
                capability.required_external_dir_hint,
                matches=matching_dirs,
                note="direct external repo path is optional when the skill is served from a consolidated Jarvis skill root",
            )
        if capability.required_skill:
            cmd = f"/{capability.required_skill}"
            c_checks["skill_scan"] = _status(cmd in skill_commands, cmd)
            c_checks["discord_exposure_advisory"] = _status(
                cmd in discord_commands,
                cmd,
                advisory=True,
                note="Discord /skill option exposure is not required for source-untouched Jarvis hosting; direct skill invocation or explicit file/URL inputs may still work.",
            )
        if capability.name == "styled_voice":
            c_checks["source_untouched_mode"] = _status(
                True,
                "Hermes source is not patched; Jarvis only hosts/verifies the skill",
                limitation="Hidden Discord attachment cache handoff cannot be guaranteed unless Hermes exposes attachment paths/URLs in the skill request context.",
            )
        if capability.health_url:
            c_checks["backend_health"] = _http_health(capability.health_url) if include_network else _status(False, "skipped; pass --include-network", skipped=True)
        capability_ok = all(
            check.get("ok") or check.get("skipped") or check.get("advisory")
            for check in c_checks.values()
        )
        capabilities[capability.name] = {
            "ok": capability_ok,
            "description": capability.description,
            "checks": c_checks,
        }

    overall_ok = all(check.get("ok") for check in checks.values()) and all(cap.get("ok") for cap in capabilities.values())
    return {
        "ok": overall_ok,
        "contract": "Hermes agent + jinwang-jarvis",
        "hermes_home": str(hermes_home),
        "hermes_agent_dir": str(hermes_agent_dir),
        "hermes_config_path": str(hermes_config_path),
        "checks": checks,
        "capabilities": capabilities,
    }
