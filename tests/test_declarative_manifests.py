from pathlib import Path

import pytest
import yaml

from zeus_os.declarative import ManifestValidationError, validate_repo_manifests


def test_repository_declarative_manifests_are_valid():
    result = validate_repo_manifests(Path.cwd())

    assert "boramae" in result.agents
    assert result.agents["boramae"].shim == "hermes"
    assert "hermes" in result.shims
    assert "news-center" in result.apps
    assert result.apps["news-center"].kind == "watchdog"
    assert "discord" in result.apps
    assert result.apps["discord"].kind == "channel"


def test_declarative_schema_documents_exist():
    agent_schema = Path("docs/schemas/agent-persona.schema.yaml")
    app_schema = Path("docs/schemas/capability-app.schema.yaml")

    assert yaml.safe_load(agent_schema.read_text(encoding="utf-8"))["kind"] == "AgentPersonaSchema"
    assert yaml.safe_load(app_schema.read_text(encoding="utf-8"))["kind"] == "CapabilityAppSchema"


def test_agent_manifest_requires_existing_shim(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agent-shim" / "hermes").mkdir(parents=True)
    (tmp_path / "apps").mkdir()
    (tmp_path / "agents" / "bad.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "zeus.os/v1alpha1",
                "kind": "AgentPersona",
                "metadata": {"name": "bad"},
                "spec": {"persona": "test", "shim": "missing-shim"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="missing-shim"):
        validate_repo_manifests(tmp_path)


def test_app_manifest_requires_known_kind(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agent-shim" / "hermes").mkdir(parents=True)
    app_dir = tmp_path / "apps" / "bad-app"
    app_dir.mkdir(parents=True)
    (app_dir / "app.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "zeus.os/v1alpha1",
                "kind": "CapabilityApp",
                "metadata": {"name": "bad-app"},
                "spec": {"kind": "unknown", "entrypoint": "README.md"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="unknown"):
        validate_repo_manifests(tmp_path)
