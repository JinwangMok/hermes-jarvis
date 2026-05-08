from __future__ import annotations

from pathlib import Path

import pytest

from zeus_os.paths import MissingRootError, UnknownRootError, ZeusPaths


def test_resolves_legacy_and_declarative_roots_from_explicit_repo_root() -> None:
    repo_root = Path.cwd()
    paths = ZeusPaths(repo_root)

    expected_roots = {
        "data": repo_root / "data",
        "state": repo_root / "state",
        "skills": repo_root / "skills",
        "scripts": repo_root / "scripts",
        "agents": repo_root / "agents",
        "agent_shim": repo_root / "agent-shim",
        "apps": repo_root / "apps",
        "channels": repo_root / "channels",
        "vmem": repo_root / "vmem",
        "journals": repo_root / "journals",
        "wiki": repo_root / "wiki",
        "assets": repo_root / "assets",
        "credentials": repo_root / "credentials",
        "workspace": repo_root / "workspace",
    }

    for name, expected in expected_roots.items():
        assert paths.resolve_root(name) == expected


def test_root_policies_mark_runtime_truth_and_secret_local_only() -> None:
    paths = ZeusPaths(Path.cwd())

    for name in ("data", "state"):
        policy = paths.root_policy(name)
        assert policy.source_of_truth == "runtime_truth"
        assert policy.category == "legacy_runtime"
        assert policy.implicit_create_allowed is False

    credentials = paths.root_policy("credentials")
    assert credentials.source_of_truth == "local_only"
    assert credentials.category == "local_private"
    assert credentials.inventory_scannable is False
    assert credentials.implicit_create_allowed is False


def test_unknown_root_raises_typed_error() -> None:
    paths = ZeusPaths(Path.cwd())

    with pytest.raises(UnknownRootError):
        paths.resolve_root("does_not_exist")


def test_missing_required_root_raises_without_implicit_create(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = ZeusPaths(repo_root)

    with pytest.raises(MissingRootError):
        paths.resolve_root("data")

    assert not (repo_root / "data").exists()
