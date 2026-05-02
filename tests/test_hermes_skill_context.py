from __future__ import annotations

import json
from pathlib import Path

from jinwang_jarvis.cli import main
from jinwang_jarvis.hermes_skill_context import generate_skill_context
from jinwang_jarvis.hermes_skill_search import build_skill_search_index


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
    assert {"name", "path", "score", "purpose", "triggers", "tags", "related", "snippet"} <= set(first)
    assert "Hermes skill search context" in result["context"]


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
