from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinwang_jarvis.cli import main
from jinwang_jarvis.hermes_skill_search import build_skill_search_index, evaluate_skill_search, search_skills


def _write_skill(
    skill_dir: Path,
    *,
    name: str | None = None,
    description: str = "",
    triggers: list[str] | None = None,
    tags: list[str] | None = None,
    related: list[str] | None = None,
    body: str = "",
    extra_frontmatter: str = "",
) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = ["---", f"name: {name or skill_dir.name}"]
    if description:
        frontmatter.append(f"description: {description}")
    if triggers:
        frontmatter.append("triggers:")
        frontmatter.extend(f"  - {item}" for item in triggers)
    if tags:
        frontmatter.append("tags:")
        frontmatter.extend(f"  - {item}" for item in tags)
    if related:
        frontmatter.append("related:")
        frontmatter.extend(f"  - {item}" for item in related)
    if extra_frontmatter:
        frontmatter.append(extra_frontmatter.rstrip())
    frontmatter.append("---")
    (skill_dir / "SKILL.md").write_text("\n".join(frontmatter) + f"\n\n# {name or skill_dir.name}\n\n{body}\n", encoding="utf-8")


def test_index_and_search_rank_relevant_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(
        root / "email-triage",
        description="Classify important email and calendar requests",
        triggers=["email triage", "inbox priority"],
        tags=["mail", "priority"],
        body="Use this for inbox triage, sender classification, and urgent reply prioritization.",
    )
    _write_skill(root / "voice-style", description="Voice sample library", tags=["audio"], body="Manage reference audio clips.")
    db_path = tmp_path / "skills.sqlite"

    index = build_skill_search_index(db_path, skill_roots=[root])
    result = search_skills(db_path, "urgent email triage", top_k=2)

    assert index["ok"] is True
    assert index["counts"]["inserted"] == 2
    assert result["ok"] is True
    assert result["rows"][0]["name"] == "email-triage"
    assert result["rows"][0]["tags"] == ["mail", "priority"]


def test_incremental_update_reindexes_changed_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill = root / "retrieval"
    _write_skill(skill, description="Search old wiki pages", tags=["wiki"], body="Find old wiki entries.")
    db_path = tmp_path / "skills.sqlite"

    first = build_skill_search_index(db_path, skill_roots=[root])
    second = build_skill_search_index(db_path, skill_roots=[root])
    _write_skill(skill, description="Search Hermes skills", tags=["hermes"], body="Find Hermes retrieval sidecar skills.")
    third = build_skill_search_index(db_path, skill_roots=[root])
    result = search_skills(db_path, "Hermes retrieval sidecar", top_k=1)

    assert first["counts"]["inserted"] == 1
    assert second["counts"]["skipped"] == 1
    assert third["counts"]["updated"] == 1
    assert result["rows"][0]["purpose"] == "Search Hermes skills"


def test_secret_redaction_before_storage_and_indexing(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    secret = "sk-live-1234567890abcdefghijklmnopqrstuv"
    _write_skill(
        root / "secure-deploy",
        description="Deploy securely",
        body=f"Use deploy checks. api_key: {secret}\nAuthorization: Bearer {secret}",
    )
    db_path = tmp_path / "skills.sqlite"

    build_skill_search_index(db_path, skill_roots=[root])
    result = search_skills(db_path, "deploy api key", top_k=1)

    payload = json.dumps(result, ensure_ascii=False)
    assert "[REDACTED_SECRET]" in payload
    assert secret not in payload


def test_pinned_boost_beats_otherwise_similar_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(root / "regular-sqlite", description="SQLite FTS search helper", body="Search SQLite FTS data.")
    pinned = root / "pinned-sqlite"
    _write_skill(pinned, description="SQLite FTS search helper", body="Search SQLite FTS data.")
    (pinned / ".usage.json").write_text(json.dumps({"pinned": True}), encoding="utf-8")
    db_path = tmp_path / "skills.sqlite"

    build_skill_search_index(db_path, skill_roots=[root])
    result = search_skills(db_path, "sqlite fts search", top_k=2)

    assert result["rows"][0]["name"] == "pinned-sqlite"
    assert result["rows"][0]["pinned"] is True


def test_negative_claim_penalty_demotes_broken_skill(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(root / "working-browser", description="Browser automation helper", body="Use browser automation for web QA.")
    _write_skill(root / "broken-browser", description="Browser automation helper", body="Browser automation does not work and is unavailable here.")
    db_path = tmp_path / "skills.sqlite"

    build_skill_search_index(db_path, skill_roots=[root])
    result = search_skills(db_path, "browser automation", top_k=2)

    assert result["rows"][0]["name"] == "working-browser"
    assert result["rows"][1]["negative_claim_count"] >= 1


def test_cli_index_and_search_json(tmp_path: Path, capsys) -> None:
    root = tmp_path / "skills"
    db_path = tmp_path / "skills.sqlite"
    _write_skill(root / "cli-skill", description="CLI JSON search skill", tags=["cli"], body="Return JSON search results.")

    index_exit = main(["hermes-skill-search-index", "--db", str(db_path), "--skill-root", str(root)])
    index_payload = json.loads(capsys.readouterr().out)
    search_exit = main(["hermes-skill-search", "--db", str(db_path), "--query", "json search", "--top-k", "1", "--format", "json"])
    search_payload = json.loads(capsys.readouterr().out)

    assert index_exit == 0
    assert index_payload["ok"] is True
    assert search_exit == 0
    assert search_payload["ok"] is True
    assert search_payload["rows"][0]["name"] == "cli-skill"


def test_usage_recency_and_count_are_scoring_inputs(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    old = root / "old-helper"
    recent = root / "recent-helper"
    _write_skill(old, description="Jarvis helper", body="Jarvis helper search.")
    _write_skill(recent, description="Jarvis helper", body="Jarvis helper search.")
    (old / ".usage.json").write_text(json.dumps({"use_count": 1, "last_used_at": "2025-01-01T00:00:00+00:00"}), encoding="utf-8")
    (recent / ".usage.json").write_text(json.dumps({"use_count": 5, "last_used_at": "2026-04-29T00:00:00+00:00"}), encoding="utf-8")
    db_path = tmp_path / "skills.sqlite"

    build_skill_search_index(db_path, skill_roots=[root])
    result = search_skills(db_path, "jarvis helper", top_k=2, now=datetime(2026, 4, 30, tzinfo=timezone.utc))

    assert result["rows"][0]["name"] == "recent-helper"
    assert result["rows"][0]["use_count"] == 5


def test_jarvis_central_telemetry_merges_into_search_index(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    regular = root / "regular-helper"
    central = root / "central-helper"
    _write_skill(regular, description="Jarvis telemetry helper", body="Jarvis telemetry helper search.")
    _write_skill(central, description="Jarvis telemetry helper", body="Jarvis telemetry helper search.")
    telemetry_path = tmp_path / "state" / "hermes-skill-usage.json"
    telemetry_path.parent.mkdir(parents=True)
    telemetry_path.write_text(
        json.dumps({
            "version": 1,
            "skills": {
                str(central.resolve()): {
                    "name": "central-helper",
                    "path": str(central),
                    "use_count": 9,
                    "last_used_at": "2026-04-30T00:00:00+00:00",
                }
            },
        }),
        encoding="utf-8",
    )
    db_path = tmp_path / "skills.sqlite"

    index = build_skill_search_index(db_path, skill_roots=[root], telemetry_path=telemetry_path)
    result = search_skills(db_path, "jarvis telemetry helper", top_k=2, now=datetime(2026, 4, 30, tzinfo=timezone.utc))

    assert index["telemetry_path"] == str(telemetry_path)
    assert result["rows"][0]["name"] == "central-helper"
    assert result["rows"][0]["use_count"] == 9


def test_search_logging_is_opt_in_and_metadata_only(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    secret = "sk-live-1234567890abcdefghijklmnopqrstuv"
    _write_skill(root / "logged-skill", description="Logged skill", body=f"Search logging body. token: {secret}")
    db_path = tmp_path / "skills.sqlite"
    log_path = tmp_path / "state" / "search.jsonl"
    build_skill_search_index(db_path, skill_roots=[root], telemetry_path=None)

    unlogged = search_skills(db_path, "search logging", top_k=1)
    logged = search_skills(db_path, "search logging", top_k=1, search_log_path=log_path, selected_skill="logged-skill")

    event = json.loads(log_path.read_text(encoding="utf-8"))
    assert unlogged["ok"] is True
    assert logged["rows"][0]["name"] == "logged-skill"
    assert event["query"] == "search logging"
    assert event["top_k"] == 1
    assert event["returned_skill_names"] == ["logged-skill"]
    assert event["selected_skill"] == "logged-skill"
    assert secret not in log_path.read_text(encoding="utf-8")


def test_eval_metrics_and_exact_name_path_boosts(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    _write_skill(root / "hermes-jinwang-customization", description="Hermes Jinwang customization contract", body="Preserve customization checks.")
    _write_skill(root / "jinwang-jarvis", description="Jarvis source untouched sidecar", body="Source untouched Jarvis skill retrieval context budget.")
    _write_skill(root / "opencode", description="OpenCode agent workflow", body="OpenCode tmux ultrawork ulw orchestration.")
    _write_skill(root / "jinwang-opencode-tmux-team", description="OpenCode tmux team", body="tmux team panes for ulw work.")
    db_path = tmp_path / "skills.sqlite"
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(
        json.dumps({
            "queries": [
                {"query": "hermes jinwang customization", "expected_skill_names": ["hermes-jinwang-customization"]},
                {"query": "opencode tmux ulw", "expected_skill_names": ["opencode", "jinwang-opencode-tmux-team"]},
            ]
        }),
        encoding="utf-8",
    )
    build_skill_search_index(db_path, skill_roots=[root], telemetry_path=None)

    smoke = search_skills(db_path, "hermes jinwang customization", top_k=1)
    evaluation = evaluate_skill_search(db_path, gold_path, k=3)

    assert smoke["rows"][0]["name"] == "hermes-jinwang-customization"
    assert evaluation["query_count"] == 2
    assert evaluation["recall_at_k"] >= 0.75
    assert evaluation["mrr_at_k"] == 1.0


def test_cli_search_logging_and_eval_json(tmp_path: Path, capsys) -> None:
    root = tmp_path / "skills"
    db_path = tmp_path / "skills.sqlite"
    log_path = tmp_path / "state" / "search.jsonl"
    gold_path = tmp_path / "gold.json"
    _write_skill(root / "cli-eval-skill", description="CLI eval search", body="CLI eval search logging.")
    gold_path.write_text(json.dumps({"queries": [{"query": "cli eval", "expected_skill_names": ["cli-eval-skill"]}]}), encoding="utf-8")

    index_exit = main(["hermes-skill-search-index", "--db", str(db_path), "--skill-root", str(root), "--telemetry-path", ""])
    _ = capsys.readouterr()
    search_exit = main([
        "hermes-skill-search",
        "--db",
        str(db_path),
        "--query",
        "cli eval",
        "--top-k",
        "1",
        "--search-log-path",
        str(log_path),
        "--clicked-skill",
        "cli-eval-skill",
    ])
    search_payload = json.loads(capsys.readouterr().out)
    eval_exit = main(["hermes-skill-search-eval", "--db", str(db_path), "--gold", str(gold_path), "--k", "1"])
    eval_payload = json.loads(capsys.readouterr().out)

    assert index_exit == 0
    assert search_exit == 0
    assert search_payload["rows"][0]["name"] == "cli-eval-skill"
    assert json.loads(log_path.read_text(encoding="utf-8"))["clicked_skill"] == "cli-eval-skill"
    assert eval_exit == 0
    assert eval_payload["recall_at_k"] == 1.0
    assert eval_payload["mrr_at_k"] == 1.0
