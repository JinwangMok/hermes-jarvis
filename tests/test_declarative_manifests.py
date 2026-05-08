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


def test_minerva_manifest_declares_legacy_hooo_bridge_without_runtime_wiring():
    result = validate_repo_manifests(paths=ZeusPaths(Path.cwd()))
    bridge = result.apps["minerva"].compatibility_bridge

    assert bridge == {
        "legacy_root": "skills",
        "legacy_name": "hooo",
        "mode": "read-only-metadata",
        "runtime_wiring": False,
    }


def test_news_center_manifest_classifies_legacy_scripts_without_moving_them():
    result = validate_repo_manifests(paths=ZeusPaths(Path.cwd()))
    scripts = {script["path"]: script for script in result.apps["news-center"].legacy_scripts}

    assert scripts["scripts/lint_daily_hot_issues_content.py"]["role"] == "quality-gate"
    assert scripts["scripts/gate_daily_hot_issues_delivery.py"]["role"] == "quality-gate"
    assert scripts["scripts/render_daily_hot_issues_pdf.py"]["role"] == "renderer"
    assert all(script["migration"] == "classify-only" for script in scripts.values())


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


def test_compatibility_bridge_legacy_name_cannot_escape_skills_root(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agent-shim" / "hermes").mkdir(parents=True)
    app_dir = tmp_path / "apps" / "bad-bridge"
    app_dir.mkdir(parents=True)
    (app_dir / "app.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "zeus.os/v1alpha1",
                "kind": "CapabilityApp",
                "metadata": {"name": "bad-bridge"},
                "spec": {
                    "kind": "skill-set",
                    "entrypoint": "README.md",
                    "compatibilityBridge": {
                        "legacyRoot": "skills",
                        "legacyName": "../credentials",
                        "mode": "read-only-metadata",
                        "runtimeWiring": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="legacyName"):
        validate_repo_manifests(tmp_path)


def test_legacy_script_classification_path_cannot_escape_repo_root(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agent-shim" / "hermes").mkdir(parents=True)
    app_dir = tmp_path / "apps" / "bad-scripts"
    app_dir.mkdir(parents=True)
    (app_dir / "app.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "zeus.os/v1alpha1",
                "kind": "CapabilityApp",
                "metadata": {"name": "bad-scripts"},
                "spec": {
                    "kind": "tool",
                    "entrypoint": "README.md",
                    "legacyScripts": [
                        {"path": "../credentials/key.txt", "role": "tool", "migration": "classify-only"}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestValidationError, match="legacyScripts.*path"):
        validate_repo_manifests(tmp_path)
