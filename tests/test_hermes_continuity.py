from pathlib import Path

from jinwang_jarvis.hermes_continuity import check_hermes_customizations


def test_check_hermes_customizations_reports_two_component_contract(tmp_path: Path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_agent = hermes_home / "hermes-agent"
    jarvis_skills = tmp_path / "jinwang-jarvis" / "skills"
    (hermes_agent / "gateway").mkdir(parents=True)
    (hermes_agent / "hermes_cli").mkdir(parents=True)
    jarvis_skills.mkdir(parents=True)
    (hermes_home / "config.yaml").write_text(
        "skills:\n"
        "  external_dirs:\n"
        f"    - {jarvis_skills}\n",
        encoding="utf-8",
    )
    (hermes_agent / "gateway" / "run.py").write_text("# upstream Hermes source untouched\n", encoding="utf-8")
    (hermes_agent / "hermes_cli" / "commands.py").write_text("# upstream Hermes source untouched\n", encoding="utf-8")

    def fake_probe(_hermes_agent_dir, code, timeout=20):
        if "scan_skill_commands" in code:
            return True, '["/discord-voice-stt-enhance", "/styled-voice"]'
        if "discord_skill_commands_by_category" in code:
            return True, '{"commands": ["/discord-voice-stt-enhance", "/styled-voice"], "hidden": 0}'
        return False, "unexpected"

    monkeypatch.setattr("jinwang_jarvis.hermes_continuity._run_python_probe", fake_probe)

    result = check_hermes_customizations(hermes_home=hermes_home, hermes_agent_dir=hermes_agent)

    assert result["contract"] == "Hermes agent + jinwang-jarvis"
    assert result["capabilities"]["styled_voice"]["checks"]["source_untouched_mode"]["ok"] is True
    assert "Hidden Discord attachment cache" in result["capabilities"]["styled_voice"]["checks"]["source_untouched_mode"]["limitation"]
    assert result["capabilities"]["styled_voice"]["checks"]["backend_health"]["skipped"] is True
    assert result["capabilities"]["discord_voice_stt_enhance"]["ok"] is True


def test_check_hermes_customizations_reports_source_untouched_limitations(tmp_path: Path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_agent = hermes_home / "hermes-agent"
    (hermes_agent / "gateway").mkdir(parents=True)
    (hermes_agent / "hermes_cli").mkdir(parents=True)
    (hermes_home / "config.yaml").write_text("skills:\n  external_dirs: []\n", encoding="utf-8")
    (hermes_agent / "gateway" / "run.py").write_text("# upstream Hermes source untouched\n", encoding="utf-8")
    (hermes_agent / "hermes_cli" / "commands.py").write_text("# upstream Hermes source untouched\n", encoding="utf-8")
    monkeypatch.setattr("jinwang_jarvis.hermes_continuity._run_python_probe", lambda *_args, **_kwargs: (True, "[]"))

    result = check_hermes_customizations(hermes_home=hermes_home, hermes_agent_dir=hermes_agent)

    assert result["ok"] is False
    styled_checks = result["capabilities"]["styled_voice"]["checks"]
    assert styled_checks["source_untouched_mode"]["ok"] is True
    assert styled_checks["skill_scan"]["ok"] is False
    assert styled_checks["discord_exposure_advisory"]["advisory"] is True
