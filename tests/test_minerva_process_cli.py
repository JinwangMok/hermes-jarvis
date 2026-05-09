from __future__ import annotations

import json

from zeus_os.cli import main


def _payload(capsys):
    return json.loads(capsys.readouterr().out)


def test_minerva_process_contract_cli_exports_defined_thresholds(capsys):
    assert main(["minerva-process-contract"]) == 0
    payload = _payload(capsys)

    assert payload["ok"] is True
    assert payload["side_effects"] == "read-only-contract"
    assert payload["contract"]["model_version"] == "minerva.process-gate/v1"
    execute = next(phase for phase in payload["contract"]["phases"] if phase["id"] == "execute")
    assert execute["thresholds"]["parallel"] == 0.60
    assert execute["thresholds"]["safe"] == 0.85
    assert execute["thresholds"]["self_heal"] == 0.70


def test_minerva_phase_gate_cli_evaluates_scores_deterministically(capsys):
    assert main([
        "minerva-phase-gate",
        "--phase", "critic_for_plan",
        "--score", "alignment=1",
        "--score", "consensus=1",
        "--score", "clarity=1",
        "--score", "safety=1",
        "--score", "evidence=0.1",
    ]) == 0
    payload = _payload(capsys)

    assert payload["ok"] is True
    assert payload["side_effects"] == "read-only-evaluation"
    assert payload["card"]["phase"]["id"] == "critic_for_plan"
    assert payload["card"]["gate"]["allowed"] is False
    assert payload["card"]["gate"]["failed_dimensions"] == ["evidence"]
    assert payload["card"]["gate"]["next_phase"] == "idea_direction_explore"


def test_minerva_phase_gate_cli_rejects_invalid_score(capsys):
    assert main(["minerva-phase-gate", "--phase", "planning", "--score", "alignment:not-valid"]) == 1
    payload = _payload(capsys)

    assert payload["ok"] is False
    assert "expected name=value" in payload["error"]
