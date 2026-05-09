from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

API_VERSION = "zeus.os/v1alpha1"


class MigrationMapValidationError(ValueError):
    """Raised when a ZeusOS rearchitecture migration map is invalid."""


@dataclass(frozen=True)
class MigrationMapEntry:
    source: str
    target: str
    mode: str
    migration: str
    requires_approval: bool
    runtime_wiring: bool
    notes: str = ""


@dataclass(frozen=True)
class RearchitectureMigrationMap:
    name: str
    side_effects: str
    entries: tuple[MigrationMapEntry, ...]


ALLOWED_MODES = {"declarative-root", "compatibility-root", "runtime-truth", "projection-root"}
ALLOWED_MIGRATIONS = {"classify-only", "already-canonical", "no-move-without-explicit-approval"}


def load_rearchitecture_migration_map(path: Path) -> RearchitectureMigrationMap:
    doc = _load_yaml_mapping(path)
    _require(doc.get("apiVersion") == API_VERSION, path, "apiVersion must be zeus.os/v1alpha1")
    _require(doc.get("kind") == "RearchitectureMigrationMap", path, "kind must be RearchitectureMigrationMap")
    metadata = _mapping(doc.get("metadata"), path, "metadata")
    spec = _mapping(doc.get("spec"), path, "spec")
    name = _nonempty_str(metadata.get("name"), path, "metadata.name")
    side_effects = _nonempty_str(spec.get("sideEffects"), path, "spec.sideEffects")
    _require(side_effects == "declaration-only", path, "spec.sideEffects must be declaration-only")
    raw_entries = spec.get("entries")
    _require(isinstance(raw_entries, list) and bool(raw_entries), path, "spec.entries must be a non-empty list")
    entries: list[MigrationMapEntry] = []
    seen_targets: set[str] = set()
    for index, item in enumerate(raw_entries):
        field = f"spec.entries[{index}]"
        entry = _mapping(item, path, field)
        source = _safe_repo_path(_nonempty_str(entry.get("source"), path, f"{field}.source"), path, f"{field}.source")
        target = _safe_repo_path(_nonempty_str(entry.get("target"), path, f"{field}.target"), path, f"{field}.target")
        mode = _nonempty_str(entry.get("mode"), path, f"{field}.mode")
        migration = _nonempty_str(entry.get("migration"), path, f"{field}.migration")
        requires_approval = entry.get("requiresApproval")
        runtime_wiring = entry.get("runtimeWiring")
        _require(mode in ALLOWED_MODES, path, f"{field}.mode has unknown value")
        _require(migration in ALLOWED_MIGRATIONS, path, f"{field}.migration has unknown value")
        _require(isinstance(requires_approval, bool), path, f"{field}.requiresApproval must be boolean")
        _require(isinstance(runtime_wiring, bool), path, f"{field}.runtimeWiring must be boolean")
        _require(runtime_wiring is False, path, f"{field}.runtimeWiring must be false for declaration-only maps")
        _require(target not in seen_targets, path, f"duplicate target {target!r}")
        seen_targets.add(target)
        if mode == "runtime-truth":
            _require(migration == "no-move-without-explicit-approval", path, f"{field}.runtime-truth entries must be no-move-without-explicit-approval")
            _require(requires_approval is True, path, f"{field}.runtime-truth entries require approval")
        entries.append(MigrationMapEntry(
            source=source,
            target=target,
            mode=mode,
            migration=migration,
            requires_approval=requires_approval,
            runtime_wiring=runtime_wiring,
            notes=str(entry.get("notes") or ""),
        ))
    return RearchitectureMigrationMap(name=name, side_effects=side_effects, entries=tuple(entries))


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MigrationMapValidationError(f"{path}: invalid YAML: {exc}") from exc
    return _mapping(raw, path, "document")


def _mapping(value: Any, path: Path, field: str) -> dict[str, Any]:
    _require(isinstance(value, dict), path, f"{field} must be a mapping")
    return value


def _nonempty_str(value: Any, path: Path, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), path, f"{field} must be a non-empty string")
    return value.strip()


def _safe_repo_path(value: str, path: Path, field: str) -> str:
    parsed = PurePosixPath(value)
    _require(not parsed.is_absolute() and ".." not in parsed.parts and parsed.parts not in {(), (".",)}, path, f"{field} must be a safe repo-relative path")
    return value if value.endswith("/") else f"{value}/"


def _require(condition: bool, path: Path, message: str) -> None:
    if not condition:
        raise MigrationMapValidationError(f"{path}: {message}")
