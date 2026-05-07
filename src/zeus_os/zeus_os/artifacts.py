"""Artifact storage with path safety, hash verification, and atomic writes."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ids, safety, store


def _safe_component(value: str, label: str) -> str:
    p = Path(value)
    if not value or p.name != value or not safety.is_safe_relative_path(value):
        raise ValueError(f"Unsafe {label}: {value}")
    return value


def _artifact_uri(task_id: str, name: str, work_order_id: str | None = None) -> str:
    safe_task_id = _safe_component(task_id, "task_id")
    safe_name = _safe_component(name, "artifact name")
    if work_order_id:
        safe_work_order_id = _safe_component(work_order_id, "work_order_id")
        return str(Path(safe_task_id) / safe_work_order_id / safe_name)
    return str(Path(safe_task_id) / safe_name)


def _artifact_dir(artifact_root: Path, task_id: str, work_order_id: str | None = None) -> Path:
    uri = _artifact_uri(task_id, ".placeholder", work_order_id)
    return safety.resolve_safe_path(artifact_root, uri).parent


def write_artifact(
    artifact_root: Path,
    task_id: str,
    name: str,
    kind: str,
    data: bytes,
    *,
    work_order_id: str | None = None,
    media_type: str | None = None,
    description: str = "",
    visibility: str = "internal",
    created_by: str | None = None,
    provenance: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_name = _safe_component(name, "artifact name")
    uri = _artifact_uri(task_id, safe_name, work_order_id)
    target_path = safety.resolve_safe_path(artifact_root, uri)
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_path = target_dir / f".{safe_name}.{ids.generate_id('artifact_tmp')}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temp_path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            os.fsync(f.fileno())
        os.replace(temp_path, target_path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise

    size_bytes = len(data)
    sha256 = safety.sha256_hex(data)

    return {
        "artifact_id": ids.generate_id("artifact"),
        "task_id": task_id,
        "work_order_id": work_order_id,
        "name": safe_name,
        "description": description,
        "kind": kind,
        "media_type": media_type or _guess_media_type(safe_name),
        "uri": uri,
        "visibility": visibility,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "provenance_json": store.json_dumps(provenance or {}),
        "metadata_json": store.json_dumps(metadata or {}),
        "created_by": created_by,
        "created_at": store.now_utc(),
    }


def register_artifact(conn: sqlite3.Connection, record: dict[str, Any]) -> str:
    record = dict(record)
    for k in ["provenance_json", "metadata_json"]:
        if isinstance(record.get(k), dict):
            record[k] = store.json_dumps(record[k])
    columns = [
        "artifact_id", "task_id", "work_order_id", "name", "description",
        "kind", "media_type", "uri", "visibility", "sha256", "size_bytes",
        "provenance_json", "metadata_json", "created_by", "created_at",
    ]
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO artifacts ({', '.join(columns)}) VALUES ({placeholders})",
        tuple(record.get(c) for c in columns),
    )
    return record["artifact_id"]


def read_artifact(artifact_root: Path, task_id: str, uri: str) -> bytes:
    target = safety.resolve_safe_path(artifact_root, uri)
    if not target.exists():
        raise FileNotFoundError(f"Artifact not found: {uri}")
    return target.read_bytes()


def reconcile_artifacts(conn: sqlite3.Connection, artifact_root: Path) -> dict[str, Any]:
    cursor = conn.execute("SELECT artifact_id, task_id, work_order_id, uri, sha256 FROM artifacts")
    missing_files = []
    hash_mismatches = []
    unregistered_files = []

    for row in cursor.fetchall():
        artifact_id, task_id, work_order_id, uri, expected_hash = row
        try:
            file_path = safety.resolve_safe_path(artifact_root, uri)
            if not file_path.exists():
                missing_files.append({"artifact_id": artifact_id, "uri": uri})
            else:
                actual_hash = safety.compute_file_hash(file_path)
                if actual_hash != expected_hash:
                    hash_mismatches.append({"artifact_id": artifact_id, "uri": uri})
        except Exception as exc:
            missing_files.append({"artifact_id": artifact_id, "uri": uri, "error": str(exc)})

    # Find unregistered files
    for task_dir in artifact_root.iterdir():
        if not task_dir.is_dir():
            continue
        for item in task_dir.rglob("*"):
            if item.is_file() and not item.name.endswith(".tmp"):
                rel = str(item.relative_to(artifact_root))
                cur = conn.execute("SELECT 1 FROM artifacts WHERE uri = ?", (rel,))
                if not cur.fetchone():
                    unregistered_files.append({"path": str(item), "relative": rel})

    return {
        "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
        "unregistered_files": unregistered_files,
    }


def _guess_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".json": "application/json",
        ".jsonl": "application/jsonlines",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".py": "text/x-python",
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".csv": "text/csv",
    }
    return mapping.get(ext, "application/octet-stream")
