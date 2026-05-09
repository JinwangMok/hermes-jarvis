from pathlib import Path

import pytest
import yaml

from zeus_os.cli import main
from zeus_os.rearchitecture_map import MigrationMapValidationError, load_rearchitecture_migration_map


def test_repository_rearchitecture_migration_map_declares_all_user_requested_roots():
    migration_map = load_rearchitecture_migration_map(Path("docs/migration/zeus-os-rearchitecture-map.yaml"))
    by_target = {entry.target: entry for entry in migration_map.entries}

    for target in (
        "agents/",
        "agent-shim/",
        "apps/",
        "channels/",
        "vmem/",
        "journals/",
        "wiki/",
        "assets/",
        "credentials/",
        "workspace/",
    ):
        assert target in by_target

    for runtime_truth in ("credentials/", "data/", "state/"):
        assert by_target[runtime_truth].mode == "runtime-truth"
        assert by_target[runtime_truth].migration == "no-move-without-explicit-approval"
        assert by_target[runtime_truth].requires_approval is True


def test_rearchitecture_migration_map_is_declaration_only_and_no_live_wiring():
    migration_map = load_rearchitecture_migration_map(Path("docs/migration/zeus-os-rearchitecture-map.yaml"))

    assert migration_map.side_effects == "declaration-only"
    assert all(entry.runtime_wiring is False for entry in migration_map.entries)
    assert any(entry.source == "skills/" and entry.target == "apps/skill-sets/" for entry in migration_map.entries)


def test_rearchitecture_migration_map_rejects_path_escape(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({
        "apiVersion": "zeus.os/v1alpha1",
        "kind": "RearchitectureMigrationMap",
        "metadata": {"name": "bad"},
        "spec": {
            "sideEffects": "declaration-only",
            "entries": [{
                "source": "scripts/",
                "target": "../credentials/",
                "mode": "declarative-root",
                "migration": "classify-only",
                "requiresApproval": True,
                "runtimeWiring": False,
            }],
        },
    }), encoding="utf-8")

    with pytest.raises(MigrationMapValidationError, match="target"):
        load_rearchitecture_migration_map(bad)


def test_rearchitecture_migration_map_status_cli_reports_runtime_truth_guards(capsys):
    assert main(["rearchitecture-map-status", "--map", "docs/migration/zeus-os-rearchitecture-map.yaml"]) == 0
    payload = yaml.safe_load(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["side_effects"] == "declaration-only"
    assert set(payload["runtime_truth"]) == {"credentials/", "data/", "state/"}
    assert any(entry["target"] == "apps/skill-sets/" and entry["migration"] == "classify-only" for entry in payload["entries"])
