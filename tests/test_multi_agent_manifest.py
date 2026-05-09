from pathlib import Path

import yaml

from zeus_os.declarative import validate_repo_manifests


EXPECTED_AGENTS = {
    "minerva": "command_governor",
    "boramae": "discord_conversation",
    "athena": "plan_critic",
    "hephaestus": "builder",
    "apollo": "reviewer",
    "artemis": "research_scout",
    "janus": "memory_evolution",
}


def _agent_manifest(name: str) -> dict:
    return yaml.safe_load((Path("agents") / f"{name}.yaml").read_text(encoding="utf-8"))


def test_zeusos_declares_greek_myth_multi_agent_roster():
    result = validate_repo_manifests(Path.cwd())

    for agent, role in EXPECTED_AGENTS.items():
        assert agent in result.agents
        manifest = _agent_manifest(agent)
        assert manifest["spec"]["role"] == role
        assert manifest["spec"]["shim"] == "hermes"
        assert manifest["spec"]["mythology"]["pantheon"] in {"greek", "roman"}
        assert manifest["spec"]["kanban"]["enabled"] is True
        assert manifest["spec"]["kanban"]["assignee"] == agent


def test_minerva_is_the_only_command_governor_and_boramae_is_conversation_surface():
    manifests = [_agent_manifest(path.stem) for path in Path("agents").glob("*.yaml")]
    governors = [m["metadata"]["name"] for m in manifests if m["spec"].get("role") == "command_governor"]

    assert governors == ["minerva"]
    assert _agent_manifest("boramae")["spec"]["reportsTo"] == "minerva"
    assert "discord" in _agent_manifest("boramae")["spec"]["channels"]


def test_all_agent_phases_require_self_justification_and_numeric_gate():
    for agent in EXPECTED_AGENTS:
        manifest = _agent_manifest(agent)
        justification = manifest["spec"]["selfJustification"]
        assert justification["requiredEveryPhase"] is True
        assert justification["minimumQuestions"] >= 2
        assert 0.0 < float(justification["minimumConfidenceThreshold"]) <= 1.0
        assert justification["evidenceRequired"] is True
