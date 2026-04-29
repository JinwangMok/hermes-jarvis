from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinwang_jarvis.cli import main
from jinwang_jarvis.hermes_skill_lifecycle import audit_hermes_skill_lifecycle, record_skill_telemetry


def _write_skill(path: Path, body: str = "Do the thing.") -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        "---\n"
        f"name: {path.name}\n"
        f"description: {path.name} skill\n"
        "---\n\n"
        f"# {path.name}\n\n{body}\n",
        encoding="utf-8",
    )


def test_audit_hermes_skill_lifecycle_classifies_usage_and_archive_candidates(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    skills_root = hermes_home / "skills"
    active = skills_root / "active-skill"
    stale = skills_root / "stale-skill"
    pinned = skills_root / "pinned-rare-skill"
    archived = skills_root / ".archive" / "old-skill"
    for skill in (active, stale, pinned, archived):
        _write_skill(skill)

    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    (active / ".usage.json").write_text(json.dumps({"last_used_at": (now - timedelta(days=2)).isoformat(), "use_count": 4}), encoding="utf-8")
    (stale / ".usage.json").write_text(json.dumps({"last_used_at": (now - timedelta(days=120)).isoformat(), "use_count": 1}), encoding="utf-8")
    (pinned / ".usage.json").write_text(json.dumps({"last_used_at": (now - timedelta(days=365)).isoformat(), "pinned": True}), encoding="utf-8")
    (archived / ".usage.json").write_text(json.dumps({"state": "archived", "archived_at": now.isoformat()}), encoding="utf-8")

    result = audit_hermes_skill_lifecycle(
        hermes_home=hermes_home,
        hermes_config_path=hermes_home / "config.yaml",
        now=now,
        stale_after_days=30,
        archive_after_days=90,
    )

    assert result["ok"] is True
    assert result["summary"]["total_skills"] == 4
    assert result["summary"]["active"] == 2
    assert result["summary"]["stale"] == 1
    assert result["summary"]["archived"] == 1
    assert result["summary"]["pinned"] == 1
    assert any(item["name"] == "stale-skill" and item["recommended_action"] == "archive_candidate" for item in result["skills"])
    assert any(item["name"] == "pinned-rare-skill" and item["recommended_action"] == "keep_pinned" for item in result["skills"])


def test_audit_hermes_skill_lifecycle_detects_negative_claim_revalidation(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    skill = hermes_home / "skills" / "old-negative-claim"
    _write_skill(skill, "The browser tools do not work in this environment. X command is unavailable.")
    now = datetime(2026, 4, 29, tzinfo=timezone.utc)
    (skill / ".usage.json").write_text(json.dumps({"last_patched_at": (now - timedelta(days=45)).isoformat()}), encoding="utf-8")

    result = audit_hermes_skill_lifecycle(
        hermes_home=hermes_home,
        hermes_config_path=hermes_home / "config.yaml",
        now=now,
        negative_claim_ttl_days=14,
    )

    entry = result["skills"][0]
    assert entry["negative_claims"]["count"] >= 2
    assert entry["negative_claims"]["revalidate"] is True
    assert "negative_claim_revalidation" in entry["recommendations"]


def test_cli_exposes_passive_lifecycle_audit(tmp_path: Path, capsys) -> None:
    hermes_home = tmp_path / "hermes"
    _write_skill(hermes_home / "skills" / "cli-skill")

    exit_code = main([
        "hermes-skill-lifecycle-audit",
        "--hermes-home",
        str(hermes_home),
        "--no-external-dirs",
    ])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["mode"] == "passive_source_untouched_skill_lifecycle_audit"
    assert payload["summary"]["total_skills"] == 1
    assert payload["skills"][0]["name"] == "cli-skill"


def test_audit_hermes_skill_lifecycle_includes_jarvis_external_dirs_from_config(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    external_skills = tmp_path / "jinwang-jarvis" / "skills"
    _write_skill(external_skills / "jarvis-owned")
    (hermes_home / "config.yaml").parent.mkdir(parents=True, exist_ok=True)
    (hermes_home / "config.yaml").write_text(
        "skills:\n"
        "  external_dirs:\n"
        f"    - {external_skills}\n",
        encoding="utf-8",
    )

    result = audit_hermes_skill_lifecycle(hermes_home=hermes_home, hermes_config_path=hermes_home / "config.yaml")

    assert any(root["path"] == str(external_skills) and root["kind"] == "external" for root in result["roots"])
    assert result["skills"][0]["source"] == "external"
    assert result["skills"][0]["name"] == "jarvis-owned"


def test_record_skill_telemetry_writes_jarvis_sidecar_and_audit_consumes_it(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    skill = hermes_home / "skills" / "telemetry-skill"
    telemetry_path = tmp_path / "jarvis" / "state" / "hermes-skill-usage.json"
    _write_skill(skill)
    now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)

    first = record_skill_telemetry(
        skill="telemetry-skill",
        event="viewed",
        hermes_home=hermes_home,
        hermes_config_path=hermes_home / "config.yaml",
        telemetry_path=telemetry_path,
        now=now,
    )
    second = record_skill_telemetry(
        skill="telemetry-skill",
        event="used",
        hermes_home=hermes_home,
        hermes_config_path=hermes_home / "config.yaml",
        telemetry_path=telemetry_path,
        now=now + timedelta(minutes=5),
    )

    assert first["ok"] is True
    assert second["usage"]["use_count"] == 1
    assert telemetry_path.exists()

    audit = audit_hermes_skill_lifecycle(
        hermes_home=hermes_home,
        hermes_config_path=hermes_home / "config.yaml",
        telemetry_path=telemetry_path,
        now=now + timedelta(minutes=10),
    )

    entry = audit["skills"][0]
    assert entry["usage_metadata_present"] is True
    assert entry["usage_metadata_source"] == "jarvis_telemetry"
    assert entry["use_count"] == 1
    assert entry["last_used_at"] == (now + timedelta(minutes=5)).isoformat()


def test_cli_records_skill_telemetry(tmp_path: Path, capsys) -> None:
    hermes_home = tmp_path / "hermes"
    telemetry_path = tmp_path / "jarvis" / "state" / "hermes-skill-usage.json"
    _write_skill(hermes_home / "skills" / "cli-telemetry-skill")

    exit_code = main([
        "hermes-skill-telemetry",
        "record",
        "--skill",
        "cli-telemetry-skill",
        "--event",
        "used",
        "--hermes-home",
        str(hermes_home),
        "--telemetry-path",
        str(telemetry_path),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["usage"]["use_count"] == 1
