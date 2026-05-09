from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mail-secretary-watchdog.py"


def load_watchdog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("mail_secretary_watchdog", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO", tmp_path)
    monkeypatch.setattr(module, "CONFIG", "config/test.yaml")
    monkeypatch.setattr(module, "STATE_FILE", tmp_path / "state" / "watchdog.json")
    monkeypatch.setattr(module, "database_path", lambda: tmp_path / "state" / "test.db")
    monkeypatch.setattr(module, "message_meta", lambda message_ids: {})
    return module


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["watchdog-test"], returncode, stdout=stdout, stderr=stderr)


def arrange_triage_artifact(tmp_path: Path, cases: list[dict[str, object]]) -> str:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return json.dumps({"artifact_path": str(artifact_path)})


def test_main_is_silent_when_no_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    module = load_watchdog(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "run", lambda cmd: completed(stdout=arrange_triage_artifact(tmp_path, [])))

    assert module.main() == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert not module.STATE_FILE.exists()


def test_main_suppresses_duplicate_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    module = load_watchdog(tmp_path, monkeypatch)
    case = {
        "case_id": "case-1",
        "source_message_id": "msg-1",
        "triage_kind": "reply",
        "action_type": "draft_reply",
        "risk_level": "low",
        "meaning_summary": "hello",
    }
    monkeypatch.setattr(module, "run", lambda cmd: completed(stdout=arrange_triage_artifact(tmp_path, [case])))

    assert module.main() == 0
    first = capsys.readouterr()
    assert "새 메일 1건" in first.out

    assert module.main() == 0
    second = capsys.readouterr()
    assert second.out == ""
    assert second.err == ""


def test_render_and_degraded_redact_secret_like_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    module = load_watchdog(tmp_path, monkeypatch)
    monkeypatch.setattr(
        module,
        "message_meta",
        lambda message_ids: {
            "msg-secret": {
                "from_addr": "ops@example.com",
                "subject": "token=abc123 password: hunter2",
                "sent_at": "",
                "snippet": "Bearer abc.def.ghi and sk-liveabcdefghijklmnopqrstuvwxyz",
            }
        },
    )
    rendered = module.render_new_cases(
        [
            {
                "case_id": "case-secret",
                "source_message_id": "msg-secret",
                "body_excerpt": "api_key=XYZ-123 secret: supersecret token abcdef",
                "meaning_summary": "contains password=hunter2",
                "approval_card_md": "Use Authorization: Bearer real-token and sk-test1234567890",
            }
        ]
    )

    assert "hunter2" not in rendered
    assert "XYZ-123" not in rendered
    assert "real-token" not in rendered
    assert "sk-test1234567890" not in rendered
    assert "[REDACTED]" in rendered

    assert module.degraded("unit", completed(stderr="password=opensesame\nAuthorization: Bearer live-token")) == 0
    degraded = capsys.readouterr().out
    assert "opensesame" not in degraded
    assert "live-token" not in degraded
    assert "[REDACTED]" in degraded


def test_artifact_read_degraded_redacts_secret_like_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    module = load_watchdog(tmp_path, monkeypatch)
    missing = tmp_path / "missing-token=artifact-secret.json"
    monkeypatch.setattr(module, "run", lambda cmd: completed(stdout=json.dumps({"artifact_path": str(missing)})))

    assert module.main() == 0

    output = capsys.readouterr().out
    assert "artifact-secret" not in output
    assert "[REDACTED]" in output


def test_save_state_uses_restrictive_tempfile_without_predictable_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = load_watchdog(tmp_path, monkeypatch)
    predictable_tmp = module.STATE_FILE.with_suffix(".tmp")

    module.save_state({"delivered_cases": {"case-1": "fp"}})

    assert json.loads(module.STATE_FILE.read_text(encoding="utf-8")) == {"delivered_cases": {"case-1": "fp"}}
    assert not predictable_tmp.exists()
    mode = stat.S_IMODE(module.STATE_FILE.stat().st_mode)
    assert mode == 0o600
    assert not os.path.islink(module.STATE_FILE)
