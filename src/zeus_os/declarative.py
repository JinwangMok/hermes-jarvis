from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import json
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
    path: Path


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
    compatibility_bridge: dict[str, Any] | None = None
    legacy_scripts: tuple[dict[str, str], ...] = ()
    runtime_bindings: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class ManifestValidationResult:
    agents: dict[str, AgentManifest]
    shims: dict[str, ShimManifest]
    apps: dict[str, AppManifest]


@dataclass(frozen=True)
class RegistryEntry:
    category: str
    name: str
    kind: str
    path: Path
    source_root: str
    entrypoint: str | None = None
    legacy_scripts: tuple[dict[str, str], ...] = ()
    compatibility_bridge: dict[str, Any] | None = None
    runtime_bindings: tuple[dict[str, str], ...] = ()


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


def list_registry(
    repo_root: Path | None = None,
    *,
    paths: ZeusPaths | None = None,
) -> tuple[RegistryEntry, ...]:
    manifests = validate_repo_manifests(repo_root, paths=paths)
    entries: list[RegistryEntry] = []
    for agent in manifests.agents.values():
        entries.append(
            RegistryEntry(
                category="agent",
                name=agent.name,
                kind="AgentPersona",
                path=agent.path,
                source_root="agents",
            )
        )
    for shim in manifests.shims.values():
        entries.append(
            RegistryEntry(
                category="shim",
                name=shim.name,
                kind="AgentShim",
                path=shim.path,
                source_root="agent_shim",
            )
        )
    for app in manifests.apps.values():
        is_channel = app.kind == "channel"
        entries.append(
            RegistryEntry(
                category="channel" if is_channel else "app",
                name=app.name,
                kind=app.kind,
                path=app.path,
                source_root="channels" if is_channel else "apps",
                entrypoint=app.entrypoint,
                compatibility_bridge=app.compatibility_bridge,
                legacy_scripts=app.legacy_scripts,
                runtime_bindings=app.runtime_bindings,
            )
        )
    return tuple(sorted(entries, key=lambda entry: (entry.category, entry.name)))


def list_automation_inventory(
    repo_root: Path | None = None,
    *,
    paths: ZeusPaths | None = None,
    hermes_jobs_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return a read-only app-to-live-automation view without leaking prompts."""
    manifests = validate_repo_manifests(repo_root, paths=paths)
    live_jobs = _load_hermes_cron_jobs(hermes_jobs_path)
    jobs_by_name = {str(job.get("name") or ""): job for job in live_jobs if isinstance(job, dict)}
    inventory: list[dict[str, Any]] = []
    for app in sorted(manifests.apps.values(), key=lambda item: item.name):
        for binding in app.runtime_bindings:
            job = jobs_by_name.get(binding["name"])
            live = {"status": "missing"}
            if job:
                live = {
                    "status": "matched",
                    "id": str(job.get("id") or ""),
                    "name": str(job.get("name") or ""),
                    "schedule": str(job.get("schedule") or ""),
                    "enabled": bool(job.get("enabled", False)),
                    "script": str(job.get("script") or ""),
                    "workdir": str(job.get("workdir") or ""),
                }
            inventory.append({
                "app": app.name,
                "kind": app.kind,
                "declared": dict(binding),
                "live": live,
                "side_effects": "read-only-inventory",
            })
    return inventory


def _load_hermes_cron_jobs(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return [job for job in data["jobs"] if isinstance(job, dict)]
    if isinstance(data, list):
        return [job for job in data if isinstance(job, dict)]
    return []


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
        agents[name] = AgentManifest(name=name, persona=persona, shim=shim, path=path)
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
        compatibility_bridge = _optional_compatibility_bridge(spec.get("compatibilityBridge"), path)
        legacy_scripts = _optional_legacy_scripts(spec.get("legacyScripts"), path)
        runtime_bindings = _optional_runtime_bindings(spec.get("runtimeBindings"), path)
        _require(kind in ALLOWED_APP_KINDS, path, f"unknown app kind {kind!r}")
        _require(name not in apps, path, f"duplicate app {name!r}")
        apps[name] = AppManifest(
            name=name,
            kind=kind,
            entrypoint=entrypoint,
            path=path.parent,
            compatibility_bridge=compatibility_bridge,
            legacy_scripts=legacy_scripts,
            runtime_bindings=runtime_bindings,
        )
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


def _optional_compatibility_bridge(value: Any, path: Path) -> dict[str, Any] | None:
    if value is None:
        return None
    bridge = _mapping(value, path, "spec.compatibilityBridge")
    legacy_root = _nonempty_str(bridge.get("legacyRoot"), path, "spec.compatibilityBridge.legacyRoot")
    legacy_name = _nonempty_str(bridge.get("legacyName"), path, "spec.compatibilityBridge.legacyName")
    _require(_is_single_relative_name(legacy_name), path, "spec.compatibilityBridge.legacyName must be a single relative name")
    mode = _nonempty_str(bridge.get("mode"), path, "spec.compatibilityBridge.mode")
    runtime_wiring = bridge.get("runtimeWiring")
    _require(isinstance(runtime_wiring, bool), path, "spec.compatibilityBridge.runtimeWiring must be a boolean")
    _require(legacy_root == "skills", path, "spec.compatibilityBridge.legacyRoot must be skills")
    _require(mode == "read-only-metadata", path, "spec.compatibilityBridge.mode must be read-only-metadata")
    _require(runtime_wiring is False, path, "spec.compatibilityBridge.runtimeWiring must be false")
    return {
        "legacy_root": legacy_root,
        "legacy_name": legacy_name,
        "mode": mode,
        "runtime_wiring": runtime_wiring,
    }


def _optional_legacy_scripts(value: Any, path: Path) -> tuple[dict[str, str], ...]:
    if value is None:
        return ()
    _require(isinstance(value, list), path, "spec.legacyScripts must be a list")
    scripts: list[dict[str, str]] = []
    for index, item in enumerate(value):
        field = f"spec.legacyScripts[{index}]"
        script = _mapping(item, path, field)
        script_path = _nonempty_str(script.get("path"), path, f"{field}.path")
        role = _nonempty_str(script.get("role"), path, f"{field}.role")
        migration = _nonempty_str(script.get("migration"), path, f"{field}.migration")
        _require(_is_repo_relative_script_path(script_path), path, f"{field}.path must be a repo-relative scripts/ path")
        _require(role in {"watchdog", "tool", "renderer", "quality-gate", "installer"}, path, f"{field}.role has unknown classification")
        _require(migration == "classify-only", path, f"{field}.migration must be classify-only")
        scripts.append({"path": script_path, "role": role, "migration": migration})
    return tuple(scripts)


def _optional_runtime_bindings(value: Any, path: Path) -> tuple[dict[str, str], ...]:
    if value is None:
        return ()
    _require(isinstance(value, list), path, "spec.runtimeBindings must be a list")
    bindings: list[dict[str, str]] = []
    for index, item in enumerate(value):
        field = f"spec.runtimeBindings[{index}]"
        binding = _mapping(item, path, field)
        binding_type = _nonempty_str(binding.get("type"), path, f"{field}.type")
        name = _nonempty_str(binding.get("name"), path, f"{field}.name")
        script = _nonempty_str(binding.get("script"), path, f"{field}.script")
        mode = _nonempty_str(binding.get("mode"), path, f"{field}.mode")
        _require(binding_type == "hermes-cron", path, f"{field}.type must be hermes-cron")
        _require(_is_safe_runtime_binding_name(name), path, f"{field}.name must be a safe runtime binding name")
        _require(_is_repo_relative_script_path(script), path, f"{field}.script must be a repo-relative scripts/ path")
        _require(mode == "inventory-only", path, f"{field}.mode must be inventory-only")
        bindings.append({"type": binding_type, "name": name, "script": script, "mode": mode})
    return tuple(bindings)


def _is_repo_relative_script_path(value: str) -> bool:
    parsed = PurePosixPath(value)
    return not parsed.is_absolute() and ".." not in parsed.parts and len(parsed.parts) >= 2 and parsed.parts[0] == "scripts"


def _is_safe_runtime_binding_name(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in {"-", "_", "."} for ch in value)


def _is_single_relative_name(value: str) -> bool:
    parsed = PurePosixPath(value)
    return not parsed.is_absolute() and len(parsed.parts) == 1 and parsed.parts[0] not in {".", ".."}


def _require(condition: bool, path: Path, message: str) -> None:
    if not condition:
        raise ManifestValidationError(f"{path}: {message}")
