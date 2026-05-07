"""Adapter manifest and browser recipe dry-run contracts for Zeus OS."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import artifacts, ids, safety, store

ADAPTER_MANIFEST_VERSION = 1
BROWSER_RECIPE_VERSION = 1
_ALLOWED_ADAPTER_KINDS = {"hermes_profile", "k_skill_cli", "opencode_worker", "browser_harness"}
_REQUIRED_RECIPE_FIELDS = {"recipe_id", "version", "origin", "url_patterns", "steps", "provenance"}
_SENSITIVE_FIELD_TOKENS = (
    "password",
    "passwd",
    "cookie",
    "authorization",
    "auth_header",
    "access_token",
    "refresh_token",
    "id_token",
    "api_key",
    "apikey",
    "secret",
    "localstorage",
    "sessionstorage",
    "chain_of_thought",
    "reasoning_trace",
    "raw_reasoning",
    "hidden_reasoning",
    "private_thought",
    "internal_monologue",
)


def load_json_file(path: Path | str) -> dict[str, Any]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("JSON file must contain an object")
    return loaded


def _find_sensitive_keys(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_norm = str(key).lower().replace("-", "_")
            child_path = f"{path}.{key}"
            if any(token in key_norm for token in _SENSITIVE_FIELD_TOKENS):
                findings.append(child_path)
            findings.extend(_find_sensitive_keys(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            findings.extend(_find_sensitive_keys(child, f"{path}[{idx}]"))
    return findings


def _redact_sensitive_fields(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            key_norm = str(key).lower().replace("-", "_")
            if any(token in key_norm for token in _SENSITIVE_FIELD_TOKENS):
                result[key] = "[REDACTED: sensitive]"
            else:
                result[key] = _redact_sensitive_fields(child)
        return safety.redact_value(result)
    if isinstance(value, list):
        return [_redact_sensitive_fields(child) for child in value]
    return safety.redact_value(value)


def _json_secret_findings(value: Any) -> list[dict[str, Any]]:
    return safety.scan_for_secrets(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def validate_adapter_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if manifest.get("manifest_version") != ADAPTER_MANIFEST_VERSION:
        errors.append(f"manifest_version must be {ADAPTER_MANIFEST_VERSION}")
    if not manifest.get("adapter_id"):
        errors.append("adapter_id is required")
    if manifest.get("kind") not in _ALLOWED_ADAPTER_KINDS:
        errors.append(f"kind must be one of {sorted(_ALLOWED_ADAPTER_KINDS)}")
    if manifest.get("mode") != "dry_run":
        errors.append("mode must be dry_run for this stage")
    if manifest.get("mutation_policy") not in {"none", "proposal_only"}:
        errors.append("mutation_policy must be none or proposal_only")
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, list):
        errors.append("capabilities must be a list")
    sensitive_keys = _find_sensitive_keys(manifest)
    if sensitive_keys:
        errors.append(f"manifest contains sensitive fields: {sensitive_keys}")
    if _json_secret_findings(manifest):
        errors.append("manifest contains secret-like values")
    return {"ok": not errors, "errors": errors, "manifest": _redact_sensitive_fields(manifest)}


def validate_browser_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    missing = sorted(_REQUIRED_RECIPE_FIELDS - set(recipe))
    if missing:
        errors.append(f"missing required fields: {missing}")
    if recipe.get("version") != BROWSER_RECIPE_VERSION:
        errors.append(f"version must be {BROWSER_RECIPE_VERSION}")
    if not isinstance(recipe.get("url_patterns"), list) or not recipe.get("url_patterns"):
        errors.append("url_patterns must be a non-empty list")
    elif not all(isinstance(pattern, str) and pattern.startswith(("http://", "https://")) for pattern in recipe["url_patterns"]):
        errors.append("url_patterns must contain http(s) string patterns")
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list")
    else:
        for idx, step in enumerate(steps):
            if not isinstance(step, dict) or not step.get("action"):
                errors.append(f"steps[{idx}] must be an object with action")
    provenance = recipe.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("source"):
        errors.append("provenance.source is required")
    if recipe.get("helper_patch_policy") not in {None, "proposal_only"}:
        errors.append("helper_patch_policy must be proposal_only when present")
    sensitive_keys = _find_sensitive_keys(recipe)
    if sensitive_keys:
        errors.append(f"recipe contains sensitive fields: {sensitive_keys}")
    if _json_secret_findings(recipe):
        errors.append("recipe contains secret-like values")
    return {"ok": not errors, "errors": errors, "recipe": _redact_sensitive_fields(recipe)}


def build_dry_run_proposal(adapter_manifest: dict[str, Any], browser_recipe: dict[str, Any]) -> dict[str, Any]:
    adapter_check = validate_adapter_manifest(adapter_manifest)
    recipe_check = validate_browser_recipe(browser_recipe)
    return {
        "ok": adapter_check["ok"] and recipe_check["ok"],
        "mode": "dry_run",
        "adapter": adapter_check["manifest"],
        "browser_recipe": recipe_check["recipe"],
        "checks": {"adapter_manifest": adapter_check, "browser_recipe": recipe_check},
        "external_side_effects": [],
        "local_side_effects": ["register_internal_artifact"] if adapter_check["ok"] and recipe_check["ok"] else [],
        "blocked_actions": ["external_repo_mutation", "live_helper_patch", "browser_execution", "hermes_config_change"],
    }


def register_dry_run_proposal(
    conn: sqlite3.Connection,
    artifact_root: Path,
    *,
    task_id: str,
    adapter_manifest: dict[str, Any],
    browser_recipe: dict[str, Any],
    created_by: str = "zeus-adapter-dry-run",
) -> dict[str, Any]:
    proposal = build_dry_run_proposal(adapter_manifest, browser_recipe)
    if not proposal["ok"]:
        return proposal
    if not conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone():
        return {**proposal, "ok": False, "errors": [f"task_id not found: {task_id}"]}
    artifact_name = f"adapter-browser-recipe-dry-run-{ids.generate_id('proposal')}.json"
    record = artifacts.write_artifact(
        artifact_root,
        task_id,
        artifact_name,
        "adapter_dry_run_proposal",
        json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        media_type="application/json",
        description="Adapter manifest and browser recipe dry-run proposal",
        visibility="internal",
        created_by=created_by,
        provenance={"mode": "dry_run", "schema": "adapter_manifest+browser_recipe"},
    )
    artifact_id = None
    try:
        artifact_id = artifacts.register_artifact(conn, record)
    except Exception:
        try:
            (artifact_root / record["uri"]).unlink(missing_ok=True)
        finally:
            raise
    return {**proposal, "artifact_id": artifact_id, "artifact_uri": record["uri"]}
