import json
import sqlite3
from pathlib import Path

from zeus_os.cli import main
from zeus_os.zeus_os import adapters, schema, store


def _in_memory_store():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in store.DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


def _create_task(conn, task_id="tsk_adapter"):
    now = store.now_utc()
    conn.execute(
        "INSERT INTO tasks (task_id, title, state, budget_json, metadata_json, revision, created_at, updated_at) VALUES (?, ?, 'submitted', '{}', '{}', 1, ?, ?)",
        (task_id, "Adapter dry-run task", now, now),
    )
    return task_id


def _valid_manifest():
    return {
        "manifest_version": 1,
        "adapter_id": "browser-helper-dry-run",
        "kind": "browser_harness",
        "mode": "dry_run",
        "mutation_policy": "proposal_only",
        "capabilities": ["browser_recipe.validate", "helper_patch.propose"],
    }


def _valid_recipe():
    return {
        "recipe_id": "example-login-skip",
        "version": 1,
        "origin": "operator_observation",
        "url_patterns": ["https://example.com/*"],
        "steps": [{"action": "click", "selector": "button.skip", "description": "skip optional step"}],
        "provenance": {"source": "test-fixture", "captured_by": "zeus"},
        "helper_patch_policy": "proposal_only",
    }


def _last_json(capsys):
    out = capsys.readouterr().out.strip()
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return json.loads(lines[-1])


def test_validate_adapter_manifest_rejects_live_mutation_mode():
    manifest = _valid_manifest()
    manifest["mode"] = "live"

    result = adapters.validate_adapter_manifest(manifest)

    assert result["ok"] is False
    assert "mode must be dry_run for this stage" in result["errors"]


def test_build_dry_run_proposal_records_zero_side_effects():
    proposal = adapters.build_dry_run_proposal(_valid_manifest(), _valid_recipe())

    assert proposal["ok"] is True
    assert proposal["mode"] == "dry_run"
    assert proposal["external_side_effects"] == []
    assert proposal["local_side_effects"] == ["register_internal_artifact"]
    assert "live_helper_patch" in proposal["blocked_actions"]


def test_register_dry_run_proposal_writes_registered_artifact(tmp_path: Path):
    conn = _in_memory_store()
    task_id = _create_task(conn)

    result = adapters.register_dry_run_proposal(
        conn,
        tmp_path,
        task_id=task_id,
        adapter_manifest=_valid_manifest(),
        browser_recipe=_valid_recipe(),
    )

    assert result["ok"] is True
    row = conn.execute("SELECT uri, kind FROM artifacts WHERE artifact_id = ?", (result["artifact_id"],)).fetchone()
    assert row["kind"] == "adapter_dry_run_proposal"
    artifact_json = json.loads((tmp_path / row["uri"]).read_text(encoding="utf-8"))
    assert artifact_json["external_side_effects"] == []
    assert artifact_json["local_side_effects"] == ["register_internal_artifact"]


def test_secret_bearing_recipe_is_rejected_and_not_persisted(tmp_path: Path):
    conn = _in_memory_store()
    task_id = _create_task(conn)
    recipe = _valid_recipe()
    recipe["steps"][0]["password"] = "supersecret"

    result = adapters.register_dry_run_proposal(
        conn,
        tmp_path,
        task_id=task_id,
        adapter_manifest=_valid_manifest(),
        browser_recipe=recipe,
    )

    assert result["ok"] is False
    assert any("sensitive fields" in err for err in result["checks"]["browser_recipe"]["errors"])
    assert result["browser_recipe"]["steps"][0]["password"] == "[REDACTED: sensitive]"
    assert "supersecret" not in json.dumps(result, ensure_ascii=False)
    assert not list(tmp_path.rglob("*.json"))


def test_missing_task_id_does_not_leave_unregistered_artifact(tmp_path: Path):
    conn = _in_memory_store()

    result = adapters.register_dry_run_proposal(
        conn,
        tmp_path,
        task_id="tsk_missing",
        adapter_manifest=_valid_manifest(),
        browser_recipe=_valid_recipe(),
    )

    assert result["ok"] is False
    assert result["errors"] == ["task_id not found: tsk_missing"]
    assert not list(tmp_path.rglob("*.json"))


def test_cli_adapter_dry_run_missing_task_returns_nonzero_without_artifact(tmp_path: Path, capsys):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    main(["zeus", "init", "--workspace", str(workspace)])
    manifest_path = tmp_path / "manifest.json"
    recipe_path = tmp_path / "recipe.json"
    manifest_path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")
    recipe_path.write_text(json.dumps(_valid_recipe()), encoding="utf-8")

    ret = main([
        "zeus", "adapter", "dry-run",
        "--workspace", str(workspace),
        "--task-id", "tsk_missing",
        "--adapter-manifest", str(manifest_path),
        "--browser-recipe", str(recipe_path),
    ])
    result = _last_json(capsys)

    assert ret == 1
    assert result["ok"] is False
    assert not list((workspace / "data" / "zeus" / "tasks").rglob("*.json"))


def test_repeated_dry_runs_create_distinct_registered_artifacts(tmp_path: Path):
    conn = _in_memory_store()
    task_id = _create_task(conn)

    first = adapters.register_dry_run_proposal(
        conn,
        tmp_path,
        task_id=task_id,
        adapter_manifest=_valid_manifest(),
        browser_recipe=_valid_recipe(),
    )
    second = adapters.register_dry_run_proposal(
        conn,
        tmp_path,
        task_id=task_id,
        adapter_manifest=_valid_manifest(),
        browser_recipe=_valid_recipe(),
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert first["artifact_uri"] != second["artifact_uri"]
    reconciliation = __import__("zeus_os.zeus_os.artifacts", fromlist=["reconcile_artifacts"]).reconcile_artifacts(conn, tmp_path)
    assert reconciliation["unregistered_files"] == []
    assert reconciliation["hash_mismatches"] == []


def test_cli_adapter_dry_run_registers_proposal_artifact(tmp_path: Path, capsys):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    main(["zeus", "init", "--workspace", str(workspace)])
    main(["zeus", "task", "submit", "--workspace", str(workspace), "--title", "Adapter dry-run"])
    task_id = _last_json(capsys)["task_id"]
    manifest_path = tmp_path / "manifest.json"
    recipe_path = tmp_path / "recipe.json"
    manifest_path.write_text(json.dumps(_valid_manifest()), encoding="utf-8")
    recipe_path.write_text(json.dumps(_valid_recipe()), encoding="utf-8")

    ret = main([
        "zeus", "adapter", "dry-run",
        "--workspace", str(workspace),
        "--task-id", task_id,
        "--adapter-manifest", str(manifest_path),
        "--browser-recipe", str(recipe_path),
    ])
    result = _last_json(capsys)

    assert ret == 0
    assert result["ok"] is True
    assert result["artifact_id"].startswith("art_")
    assert len(list((workspace / "data" / "zeus" / "tasks" / task_id).glob("adapter-browser-recipe-dry-run-*.json"))) == 1
