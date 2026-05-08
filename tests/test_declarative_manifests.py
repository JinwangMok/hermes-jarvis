from pathlib import Path

import pytest
import yaml

from zeus_os.declarative import ManifestValidationError, list_registry, validate_repo_manifests
from zeus_os.paths import ZeusPaths


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


def test_manifest_validation_can_use_zeus_paths_policy():
    result = validate_repo_manifests(paths=ZeusPaths(Path.cwd()))

    assert result.agents["boramae"].shim == "hermes"
    assert result.shims["hermes"].path == Path.cwd() / "agent-shim" / "hermes"
    assert result.apps["discord"].path == Path.cwd() / "channels" / "discord"


def test_manifest_validation_still_requires_explicit_root_or_paths():
    with pytest.raises(TypeError, match="repo_root or paths"):
        validate_repo_manifests()


def test_registry_entries_are_read_only_structured_view():
    entries = list_registry(paths=ZeusPaths(Path.cwd()))
    by_key = {(entry.category, entry.name): entry for entry in entries}

    assert by_key[("agent", "boramae")].kind == "AgentPersona"
    assert by_key[("agent", "boramae")].source_root == "agents"
    assert by_key[("agent", "boramae")].path == Path.cwd() / "agents" / "boramae.yaml"
    assert by_key[("shim", "hermes")].source_root == "agent_shim"
    assert by_key[("app", "news-center")].kind == "watchdog"
    assert by_key[("channel", "discord")].source_root == "channels"


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
