from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from zeus_os.paths import ZeusPaths


API_VERSION = "zeus.os/v1alpha1"
ALLOWED_APP_KINDS = {"watchdog", "skill-set", "mcp", "tool", "a2a", "channel"}


class ManifestValidationError(ValueError):
    """Raised when a ZeusOS declarative manifest is invalid."""


@dataclass(frozen=True)
class AgentManifest:
    name: str
    persona: str
    shim: str


@dataclass(frozen=True)
class ShimManifest:
    name: str
    path: Path


@dataclass(frozen=True)
class AppManifest:
    name: str
    kind: str
    entrypoint: str
    path: Path


@dataclass(frozen=True)
class ManifestValidationResult:
    agents: dict[str, AgentManifest]
    shims: dict[str, ShimManifest]
    apps: dict[str, AppManifest]


def validate_repo_manifests(
    repo_root: Path | None = None,
    *,
    paths: ZeusPaths | None = None,
) -> ManifestValidationResult:
    if paths is not None:
        if repo_root is not None:
            raise TypeError("validate_repo_manifests accepts either repo_root or paths, not both")
        shims = _discover_shims(paths.resolve_root("agent_shim"))
        agents = _load_agents(paths.resolve_root("agents"), shims)
        apps = _load_apps(paths.resolve_root("apps"))
        channel_apps = _load_apps(paths.resolve_root("channels"))
    else:
        if repo_root is None:
            raise TypeError("validate_repo_manifests requires repo_root or paths")
        root = Path(repo_root)
        shims = _discover_shims(root / "agent-shim")
        agents = _load_agents(root / "agents", shims)
        apps = _load_apps(root / "apps")
        channel_apps = _load_apps(root / "channels")
    overlap = set(apps) & set(channel_apps)
    if overlap:
        raise ManifestValidationError(f"duplicate app names across roots: {sorted(overlap)}")
    apps.update(channel_apps)
    return ManifestValidationResult(agents=agents, shims=shims, apps=apps)


def _discover_shims(shim_root: Path) -> dict[str, ShimManifest]:
    if not shim_root.exists():
        return {}
    shims: dict[str, ShimManifest] = {}
    for child in sorted(shim_root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            shims[child.name] = ShimManifest(name=child.name, path=child)
    return shims


def _load_agents(agent_root: Path, shims: dict[str, ShimManifest]) -> dict[str, AgentManifest]:
    agents: dict[str, AgentManifest] = {}
    for path in sorted(agent_root.glob("*.yaml")) if agent_root.exists() else []:
        doc = _load_yaml_mapping(path)
        _require(doc.get("apiVersion") == API_VERSION, path, "apiVersion must be zeus.os/v1alpha1")
        _require(doc.get("kind") == "AgentPersona", path, "kind must be AgentPersona")
        metadata = _mapping(doc.get("metadata"), path, "metadata")
        spec = _mapping(doc.get("spec"), path, "spec")
        name = _nonempty_str(metadata.get("name"), path, "metadata.name")
        persona = _nonempty_str(spec.get("persona"), path, "spec.persona")
        shim = _nonempty_str(spec.get("shim"), path, "spec.shim")
        _require(shim in shims, path, f"agent {name!r} references missing shim {shim!r}")
        _require(name not in agents, path, f"duplicate agent {name!r}")
        agents[name] = AgentManifest(name=name, persona=persona, shim=shim)
    return agents


def _load_apps(app_root: Path) -> dict[str, AppManifest]:
    apps: dict[str, AppManifest] = {}
    for path in sorted(app_root.glob("**/app.yaml")) if app_root.exists() else []:
        doc = _load_yaml_mapping(path)
        _require(doc.get("apiVersion") == API_VERSION, path, "apiVersion must be zeus.os/v1alpha1")
        _require(doc.get("kind") == "CapabilityApp", path, "kind must be CapabilityApp")
        metadata = _mapping(doc.get("metadata"), path, "metadata")
        spec = _mapping(doc.get("spec"), path, "spec")
        name = _nonempty_str(metadata.get("name"), path, "metadata.name")
        kind = _nonempty_str(spec.get("kind"), path, "spec.kind")
        entrypoint = _nonempty_str(spec.get("entrypoint"), path, "spec.entrypoint")
        _require(kind in ALLOWED_APP_KINDS, path, f"unknown app kind {kind!r}")
        _require(name not in apps, path, f"duplicate app {name!r}")
        apps[name] = AppManifest(name=name, kind=kind, entrypoint=entrypoint, path=path.parent)
    return apps


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ManifestValidationError(f"{path}: invalid YAML: {exc}") from exc
    return _mapping(raw, path, "document")


def _mapping(value: Any, path: Path, field: str) -> dict[str, Any]:
    _require(isinstance(value, dict), path, f"{field} must be a mapping")
    return value


def _nonempty_str(value: Any, path: Path, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), path, f"{field} must be a non-empty string")
    return value.strip()


def _require(condition: bool, path: Path, message: str) -> None:
    if not condition:
        raise ManifestValidationError(f"{path}: {message}")
