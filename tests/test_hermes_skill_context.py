from __future__ import annotations

import json
from pathlib import Path

from zeus_os.cli import main
from zeus_os.hermes_skill_context import generate_skill_context
from zeus_os.hermes_skill_search import build_skill_search_index
from zeus_os.paths import ZeusPaths


def _write_skill(skill_dir: Path, *, name: str | None = None, body: str = "") -> None:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name or skill_dir.name}\n"
        "description: Skill context budget test helper\n"
        "triggers:\n"
        "  - context retrieval\n"
        "tags:\n"
        "  - hermes\n"
        "related:\n"
        "  - search\n"
        "---\n\n"
        f"# {name or skill_dir.name}\n\n{body}\n",
        encoding="utf-8",
    )


def test_generate_skill_context_stays_within_budget(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    long_body = "context retrieval " * 500
    for index in range(4):
        _write_skill(root / f"context-{index}", body=long_body)
    db_path = tmp_path / "skills.sqlite"

    build_skill_search_index(db_path, skill_roots=[root])
    result = generate_skill_context(db_path, "context retrieval", budget_tokens=120, top_k=4)

    assert result["ok"] is True
    assert result["estimated_tokens"] <= 120
    assert 1 <= len(result["snippets"]) <= 4
    first = result["snippets"][0]
    assert {"name", "path", "root", "source", "score", "purpose", "triggers", "tags", "related", "snippet"} <= set(first)
    assert "Hermes skill search context" in result["context"]


def test_generate_skill_context_marks_compatibility_bridge_read_only(tmp_path: Path) -> None:
    repo = tmp_path / "zeus-os"
    (repo / "agents").mkdir(parents=True)
    (repo / "agent-shim" / "hermes").mkdir(parents=True)
    (repo / "channels").mkdir(parents=True)
    (repo / "apps" / "skill-sets" / "minerva").mkdir(parents=True)
    (repo / "apps" / "skill-sets" / "minerva" / "app.yaml").write_text(
        "apiVersion: zeus.os/v1alpha1\n"
        "kind: CapabilityApp\n"
        "metadata:\n"
        "  name: minerva\n"
        "spec:\n"
        "  kind: skill-set\n"
        "  entrypoint: README.md\n"
        "  compatibilityBridge:\n"
        "    legacyRoot: skills\n"
        "    legacyName: hooo\n"
        "    mode: read-only-metadata\n"
        "    runtimeWiring: false\n",
        encoding="utf-8",
    )
    _write_skill(
        repo / "skills" / "hooo",
        name="hooo",
        body="Minerva HOOO compatibility bridge read-only metadata search context.",
    )
    db_path = tmp_path / "skills.sqlite"

    build_skill_search_index(db_path, zeus_paths=ZeusPaths(repo))
    result = generate_skill_context(db_path, "minerva hooo bridge", budget_tokens=300, top_k=1)

    assert result["ok"] is True
    snippet = result["snippets"][0]
    assert snippet["source"] == "compatibility_bridge"
    assert snippet["root"] == str(repo / "skills" / "hooo")
    assert "Source: compatibility_bridge" in result["context"]
    assert f"Root: {repo / 'skills' / 'hooo'}" in result["context"]
    assert "Read-only metadata bridge" in result["context"]
    assert "runtime_wiring false" in result["context"]


def test_cli_context_json(tmp_path: Path, capsys) -> None:
    root = tmp_path / "skills"
    db_path = tmp_path / "skills.sqlite"
    _write_skill(root / "context-cli", body="Generate context retrieval snippets for Hermes.")
    build_skill_search_index(db_path, skill_roots=[root])

    exit_code = main([
        "hermes-skill-context",
        "--db",
        str(db_path),
        "--query",
        "context retrieval",
        "--budget",
        "200",
        "--format",
        "json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["estimated_tokens"] <= 200
    assert payload["snippets"][0]["name"] == "context-cli"
