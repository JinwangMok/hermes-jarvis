from pathlib import Path

import json

from jinwang_jarvis.cli import main
from jinwang_jarvis import houroboros as houroboros_module
from jinwang_jarvis.houroboros import HouroborosWorkflow, load_run


class FakeDiscordThreadClient:
    def __init__(self):
        self.requests = []

    def create_thread(self, request):
        self.requests.append(request)
        return {
            "platform": "discord",
            "parent_channel_id": request["parent_channel_id"],
            "channel_id": request["parent_channel_id"],
            "thread_id": "fake-thread-1",
            "thread_name": request["thread_name"],
            "message_id": request["message_id"],
            "jump_url": "https://discord.test/channels/guild/channel/fake-thread-1",
            "url": "https://discord.test/thread/fake-thread-1",
            "state": "created",
        }


def _config_text(root: Path) -> str:
    return """
workspace_root: {root}
wiki_root: /home/jinwang/wiki
accounts:
  - personal
mail:
  snapshot_dir: data/snapshots/mail
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord-origin
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: zeus-os
""".format(root=root.as_posix())


def _write_config(root: Path) -> Path:
    config_file = root / "pipeline.yaml"
    config_file.write_text(_config_text(root), encoding="utf-8")
    return config_file


def _payload(capsys):
    return json.loads(capsys.readouterr().out)


def _make_seed_ready(workflow: HouroborosWorkflow, run_id: str) -> None:
    workflow.turn(run_id, "Scope: ZeusOS-owned deterministic workflow")
    workflow.turn(run_id, "Acceptance: writes deterministic artifacts")
    workflow.turn(run_id, "Constraint: no Hermes source mutation")
    workflow.turn(run_id, "Executor: deterministic-placeholder")
    workflow.turn(run_id, "Permission: seed gate approved")


def _latest_card(tmp_path: Path, run_id: str) -> dict:
    cards_path = tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl"
    return json.loads(cards_path.read_text(encoding="utf-8").splitlines()[-1])


def _proposal_components(card: dict) -> list[dict]:
    return [component for component in card["card"]["components"] if component["action"] == "select_proposal"]


def test_houroboros_state_machine_creates_artifacts_and_preserves_seed(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)

    started = workflow.start(
        goal="Build a safe local workflow",
        origin_platform="discord",
        origin_channel_id="c-1",
        origin_thread_id="t-1",
    )
    run_id = started["run_id"]
    assert started["phase"] == "interviewing"
    assert (tmp_path / "state" / "houroboros.db").exists()

    _make_seed_ready(workflow, run_id)
    turn = workflow.status(run_id)
    assert turn["phase"] == "interviewing"
    interview_path = tmp_path / "data" / "houroboros" / run_id / "interview.jsonl"
    assert interview_path.exists()
    assert "Acceptance" in interview_path.read_text(encoding="utf-8")

    seed = workflow.seed(run_id)
    seed_md = tmp_path / "data" / "houroboros" / run_id / "seed.md"
    assert seed["phase"] == "seeded"
    assert seed["seed_version"] == 1
    assert seed_md.exists()
    first_seed_text = seed_md.read_text(encoding="utf-8")

    second_seed = workflow.seed(run_id)
    assert second_seed["created"] is False
    assert second_seed["seed_version"] == 1
    assert seed_md.read_text(encoding="utf-8") == first_seed_text

    run = workflow.run(run_id)
    assert run["phase"] == "running"
    assert (tmp_path / "data" / "houroboros" / run_id / "execution_log.md").exists()

    evaluation = workflow.evaluate(run_id)
    assert evaluation["phase"] == "evaluated"
    assert evaluation["passed"] is True
    assert (tmp_path / "data" / "houroboros" / run_id / "drift.md").exists()

    evolution = workflow.evolve(run_id)
    assert evolution["phase"] == "evolved"
    assert (tmp_path / "data" / "houroboros" / run_id / "evolution.md").exists()

    status = workflow.status(run_id)
    assert status["phase"] == "evolved"
    assert status["origin"]["platform"] == "discord"
    assert "latest_drift" in status
    assert sorted(status["artifacts"]) == status["artifacts"]

    export = workflow.export(run_id)
    assert export["run"]["run_id"] == run_id
    assert export["seed"]["version"] == 1
    assert export["interview"]


def test_houroboros_evaluate_blocks_when_placeholder_evidence_missing(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Block missing evidence")
    run_id = started["run_id"]

    _make_seed_ready(workflow, run_id)
    workflow.turn(run_id, "Acceptance: criterion that must be evidenced")
    workflow.seed(run_id)
    workflow.run(run_id)
    execution_log = tmp_path / "data" / "houroboros" / run_id / "execution_log.md"
    execution_log.write_text("# Houroboros Execution Log\n\nNo matching acceptance evidence here.\n", encoding="utf-8")

    evaluation = workflow.evaluate(run_id)

    assert evaluation["phase"] == "blocked"
    assert evaluation["passed"] is False
    evaluation_text = (tmp_path / "data" / "houroboros" / run_id / "evaluation.md").read_text(encoding="utf-8")
    assert "placeholder substring match" in evaluation_text
    assert "FAIL: Acceptance: criterion that must be evidenced" in evaluation_text


def test_houroboros_auto_thread_fake_adapter_and_export_metadata(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    client = FakeDiscordThreadClient()

    started = workflow.start(
        goal="Open a task-specific Discord thread",
        origin_platform="discord",
        origin_channel_id="channel-1",
        origin_message_id="message-1",
        auto_open_thread=True,
        thread_name="hooo fake thread",
        thread_client=client,
    )

    assert client.requests[0]["parent_channel_id"] == "channel-1"
    assert started["origin"]["thread_id"] == "fake-thread-1"
    assert started["origin"]["thread"]["state"] == "created"
    assert started["origin"]["thread"]["jump_url"].endswith("fake-thread-1")
    exported = workflow.export(started["run_id"])
    assert exported["status"]["origin"]["thread"]["thread_name"] == "hooo fake thread"
    assert "origin.json" in exported["artifacts"]


class DbAwareDiscordThreadClient:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.row_existed_before_side_effect = False

    def create_thread(self, request):
        self.row_existed_before_side_effect = load_run(self.db_path, request["run_id"])["run_id"] == request["run_id"]
        return {
            "platform": "discord",
            "parent_channel_id": request["parent_channel_id"],
            "channel_id": request["parent_channel_id"],
            "thread_id": "db-aware-thread",
            "thread_name": request["thread_name"],
            "message_id": request["message_id"],
            "state": "created",
        }


def test_houroboros_reserves_db_row_before_live_thread_adapter_side_effect(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    client = DbAwareDiscordThreadClient(workflow.db_path)

    started = workflow.start(
        goal="Reserve row before live adapter",
        origin_platform="discord",
        origin_channel_id="channel-live",
        auto_open_thread=True,
        thread_client=client,
    )

    assert client.row_existed_before_side_effect is True
    assert started["origin"]["thread_id"] == "db-aware-thread"
    assert load_run(workflow.db_path, started["run_id"])["origin_thread_id"] == "db-aware-thread"


def test_houroboros_start_avoids_same_timestamp_goal_run_id_collision(tmp_path: Path, monkeypatch):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    monkeypatch.setattr(houroboros_module, "_now", lambda: "2026-05-02T00:00:00Z")

    first = workflow.start(goal="Same timestamp goal")
    second = workflow.start(goal="Same timestamp goal")

    assert first["run_id"] != second["run_id"]
    assert first["created_at"] == second["created_at"] == "2026-05-02T00:00:00Z"


def test_houroboros_pending_thread_handoff_and_mark_created(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)

    started = workflow.start(
        goal="Request Hermes/Boramae thread handoff",
        origin_platform="discord",
        origin_channel_id="channel-2",
        origin_message_id="message-2",
        auto_open_thread=True,
        thread_name="hooo pending thread",
    )
    run_id = started["run_id"]

    assert started["origin"]["thread_id"] is None
    assert started["origin"]["thread"]["state"] == "pending"
    handoff_path = tmp_path / "data" / "houroboros" / run_id / "thread_handoff.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert handoff["action"] == "discord.create_thread"
    assert handoff["request"]["thread_name"] == "hooo pending thread"

    marked = workflow.mark_thread_created(
        run_id,
        thread_id="thread-created-2",
        thread_name="created thread",
        message_id="message-created-2",
        jump_url="https://discord.test/jump",
    )
    assert marked["origin"]["thread_id"] == "thread-created-2"
    assert marked["origin"]["thread"]["state"] == "created"
    assert marked["origin"]["thread"]["message_id"] == "message-created-2"


def test_houroboros_cli_namespace_emits_json_and_exports(tmp_path: Path, capsys):
    config_file = _write_config(tmp_path)

    assert main([
        "houroboros",
        "start",
        "--config",
        str(config_file),
        "--goal",
        "Ship ZeusOS-native workflow",
        "--origin-platform",
        "discord",
        "--origin-channel-id",
        "channel-1",
        "--origin-thread-id",
        "thread-1",
    ]) == 0
    started = _payload(capsys)
    run_id = started["run_id"]
    assert started["phase"] == "interviewing"

    assert main(["houroboros", "turn", "--config", str(config_file), "--run-id", run_id, "--message", "Need seed first"]) == 0
    assert _payload(capsys)["phase"] == "interviewing"
    for message in [
        "Scope: CLI workflow",
        "Acceptance: Need seed first",
        "Constraint: no Hermes source mutation",
        "Executor: deterministic-placeholder",
        "Permission: seed gate approved",
    ]:
        assert main(["houroboros", "turn", "--config", str(config_file), "--run-id", run_id, "--message", message]) == 0
        _payload(capsys)

    for command, expected_phase in [("seed", "seeded"), ("run", "running"), ("evaluate", "evaluated"), ("evolve", "evolved")]:
        assert main(["houroboros", command, "--config", str(config_file), "--run-id", run_id]) == 0
        assert _payload(capsys)["phase"] == expected_phase

    assert main(["houroboros", "status", "--config", str(config_file), "--run-id", run_id]) == 0
    status = _payload(capsys)
    assert status["phase"] == "evolved"
    assert status["origin"]["thread_id"] == "thread-1"
    assert "seed.md" in " ".join(status["artifacts"])

    assert main(["houroboros", "export", "--config", str(config_file), "--run-id", run_id]) == 0
    exported = _payload(capsys)
    assert exported["run"]["goal"] == "Ship ZeusOS-native workflow"


def test_houroboros_cli_hooo_alias_pending_thread_and_mark_created(tmp_path: Path, capsys):
    config_file = _write_config(tmp_path)

    assert main([
        "hooo",
        "start",
        "--config",
        str(config_file),
        "--goal",
        "Ship alias Discord handoff",
        "--origin-platform",
        "discord",
        "--origin-channel-id",
        "channel-alias",
        "--origin-message-id",
        "message-alias",
        "--auto-open-thread",
        "--thread-name",
        "alias thread",
    ]) == 0
    started = _payload(capsys)
    run_id = started["run_id"]
    assert started["origin"]["thread"]["state"] == "pending"
    assert started["origin"]["thread"]["handoff"]["action"] == "discord.create_thread"

    assert main([
        "hooo",
        "mark-thread-created",
        "--config",
        str(config_file),
        "--run-id",
        run_id,
        "--thread-id",
        "thread-alias",
        "--thread-name",
        "alias created",
        "--message-id",
        "message-created",
        "--jump-url",
        "https://discord.test/alias",
    ]) == 0
    marked = _payload(capsys)
    assert marked["origin"]["thread_id"] == "thread-alias"
    assert marked["origin"]["thread"]["jump_url"] == "https://discord.test/alias"

    assert main(["hooo", "status", "--config", str(config_file), "--run-id", run_id]) == 0
    status = _payload(capsys)
    assert status["origin"]["thread"]["state"] == "created"


def test_houroboros_invalid_phase_transitions_are_rejected(tmp_path: Path, capsys):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Guard illegal transitions")
    run_id = started["run_id"]

    for command in ("run", "evaluate", "evolve"):
        assert main(["houroboros", command, "--config", str(config_file), "--run-id", run_id]) == 1
        payload = _payload(capsys)
        assert payload["ok"] is False
        assert "Invalid houroboros transition" in payload["error"]

    _make_seed_ready(workflow, run_id)
    assert main(["houroboros", "seed", "--config", str(config_file), "--run-id", run_id]) == 0
    _payload(capsys)
    assert main(["houroboros", "evolve", "--config", str(config_file), "--run-id", run_id]) == 1
    payload = _payload(capsys)
    assert "cannot evolve from phase seeded" in payload["error"]


def test_houroboros_alias_and_skill_docs_exist():
    root = Path(__file__).resolve().parents[1]
    hooo_skill = root / "skills" / "hooo" / "SKILL.md"
    houroboros_skill = root / "skills" / "houroboros" / "SKILL.md"

    assert hooo_skill.exists()
    assert houroboros_skill.exists()
    combined = hooo_skill.read_text(encoding="utf-8") + "\n" + houroboros_skill.read_text(encoding="utf-8")
    assert "Interview -> Seed -> Execute -> Evaluate -> Evolve" in combined
    assert "Hermes source" in combined
    assert "Discord thread" in combined


def test_houroboros_load_run_reports_missing_run(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)

    try:
        load_run(workflow.db_path, "missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing run should raise KeyError")



def test_houroboros_discord_interview_card_and_ambiguity_gate(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)

    started = workflow.start(goal="Design Discord-native HOOO", origin_platform="discord", origin_channel_id="parent", auto_open_thread=True)
    run_id = started["run_id"]

    state_path = tmp_path / "data" / "houroboros" / run_id / "interview_state.json"
    cards_path = tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    first_card = json.loads(cards_path.read_text(encoding="utf-8").splitlines()[0])

    assert state["ambiguity_score"] == 1.0
    assert state["seed_ready"] is False
    assert "acceptance" in state["unresolved"]
    assert first_card["action"] == "discord.interaction_message"
    assert first_card["card"]["kind"] == "interview"
    assert first_card["card"]["proposal_card"]["dimension"] == "scope"
    assert len(first_card["card"]["proposal_card"]["proposals"]) == 3
    assert first_card["card"]["buttons"] == ["select_proposal", "select_proposal", "select_proposal", "other_opinion"]

    try:
        workflow.seed(run_id)
    except ValueError as exc:
        assert "ambiguity" in str(exc)
        assert "0.2" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("seed must be blocked until ambiguity is below the gate")


def test_houroboros_interview_choices_reduce_ambiguity_and_seed_records_decisions(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Implement interactive HOOO", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]

    workflow.turn(run_id, "Scope: ZeusOS-owned HOOO only")
    workflow.turn(run_id, "Acceptance: Discord card is emitted")
    workflow.turn(run_id, "Constraint: Hermes source remains untouched")
    workflow.turn(run_id, "Executor: claude-code handoff, no direct gateway restart")
    updated = workflow.turn(run_id, "Permission: seed may be generated after ambiguity gate")

    assert updated["interview_state"]["ambiguity_score"] <= 0.2
    assert updated["interview_state"]["seed_ready"] is True
    assert updated["interview_state"]["decisions"]["executor"] == "claude-code"
    assert not updated["interview_state"]["unresolved"]

    seeded = workflow.seed(run_id)
    seed_json = json.loads((tmp_path / "data" / "houroboros" / run_id / "seed.json").read_text(encoding="utf-8"))
    assert seeded["phase"] == "seeded"
    assert seed_json["ambiguity_score"] <= 0.2
    assert seed_json["decisions"]["executor"] == "claude-code"
    assert seed_json["interview_gate"]["threshold"] == 0.2


def test_houroboros_proposal_cards_advance_each_unresolved_dimension(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Choose proposals", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]

    for expected_dimension in ["scope", "acceptance", "constraint", "executor", "permission"]:
        card = _latest_card(tmp_path, run_id)
        proposal_card = card["card"]["proposal_card"]
        assert proposal_card["dimension"] == expected_dimension
        assert len(proposal_card["proposals"]) == 3
        components = card["card"]["components"]
        assert [component["action"] for component in components] == ["select_proposal", "select_proposal", "select_proposal", "other_opinion"]
        assert [component["option_id"] for component in _proposal_components(card)] == ["a", "b", "c"]

        before = dict(workflow.status(run_id)["interview_state"]["decisions"])
        selected = _proposal_components(card)[0]
        result = workflow.handle_interaction(run_id, custom_id=selected["custom_id"], origin_channel_id="parent")
        decisions = result["interview_state"]["decisions"]
        assert expected_dimension in decisions
        for dimension in before:
            assert decisions[dimension] == before[dimension]

    final_state = workflow.status(run_id)["interview_state"]
    assert final_state["ambiguity_score"] <= 0.2
    assert final_state["seed_ready"] is True
    assert final_state["unresolved"] == []


def test_houroboros_claude_code_executor_writes_handoff_without_running_claude(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Run through Claude Code", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]
    for message in [
        "Scope: one Jarvis feature",
        "Acceptance: creates a Claude Code handoff",
        "Constraint: no live external service calls",
        "Executor: claude-code",
        "Permission: dry-run handoff only",
    ]:
        workflow.turn(run_id, message)
    workflow.seed(run_id)

    ran = workflow.run(run_id, executor="claude-code")
    handoff_path = tmp_path / "data" / "houroboros" / run_id / "claude_code_handoff.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

    assert ran["phase"] == "running"
    assert ran["execution_mode"] == "claude_code_handoff"
    assert handoff["action"] == "claude-code.execute_seed"
    assert handoff["side_effects"] == "deferred"
    assert "claude -p" in handoff["recommended_command"]
    assert "--max-turns" in handoff["recommended_command"]



def test_houroboros_freeform_turn_does_not_bypass_ambiguity_gate(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Do not bypass interview gate", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]

    status = workflow.turn(run_id, "Need seed first")

    assert status["interview_state"]["ambiguity_score"] == 1.0
    assert status["interview_state"]["seed_ready"] is False
    assert status["interview_state"]["decisions"]["notes"] == ["Need seed first"]
    try:
        workflow.seed(run_id)
    except ValueError as exc:
        assert "ambiguity" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("freeform turns must not bypass ambiguity gate")


def test_houroboros_other_opinion_routes_dimension_without_resolving_all(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Other path", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]
    card = _latest_card(tmp_path, run_id)
    other = next(component for component in card["card"]["components"] if component["action"] == "other_opinion")

    result = workflow.handle_interaction(run_id, custom_id=other["custom_id"], origin_channel_id="parent")

    assert result["interaction"]["dimension"] == "scope"
    assert result["interview_state"]["pending_freeform_dimension"] == "scope"
    assert result["interview_state"]["ambiguity_score"] == 1.0
    assert result["interview_state"]["seed_ready"] is False
    assert result["interview_state"]["unresolved"] == ["scope", "acceptance", "constraint", "executor", "permission"]

    followup_card = _latest_card(tmp_path, run_id)
    selected = _proposal_components(followup_card)[0]
    after_choice = workflow.handle_interaction(run_id, custom_id=selected["custom_id"], origin_channel_id="parent")
    assert after_choice["interview_state"]["decisions"]["scope"]
    assert "pending_freeform_dimension" not in after_choice["interview_state"]
    assert after_choice["interview_state"]["unresolved"] == ["acceptance", "constraint", "executor", "permission"]


def test_houroboros_other_opinion_plain_reply_resolves_only_pending_dimension(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Other plain reply", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]
    card = _latest_card(tmp_path, run_id)
    other = next(component for component in card["card"]["components"] if component["action"] == "other_opinion")
    workflow.handle_interaction(run_id, custom_id=other["custom_id"], origin_channel_id="parent")

    status = workflow.turn(run_id, "Only touch ZeusOS-owned runtime and tests")

    assert status["interview_state"]["decisions"]["scope"] == "Only touch ZeusOS-owned runtime and tests"
    assert "pending_freeform_dimension" not in status["interview_state"]
    assert status["interview_state"]["resolved"] == ["scope"]
    assert status["interview_state"]["unresolved"] == ["acceptance", "constraint", "executor", "permission"]
    assert status["interview_state"]["ambiguity_score"] == 0.8
    assert status["interview_state"]["seed_ready"] is False


def test_houroboros_seed_requires_all_dimensions_even_at_threshold(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Do not seed with one unresolved dimension", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]
    for message in [
        "Scope: one Jarvis feature",
        "Acceptance: targeted tests pass",
        "Constraint: no external side effects",
        "Executor: opencode",
    ]:
        status = workflow.turn(run_id, message)

    assert status["interview_state"]["ambiguity_score"] == 0.2
    assert status["interview_state"]["seed_ready"] is False
    assert status["interview_state"]["unresolved"] == ["permission"]
    try:
        workflow.seed(run_id)
    except ValueError as exc:
        assert "unresolved interview dimensions" in str(exc)
        assert "permission" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("seed must be blocked until every required interview dimension is resolved")



def test_houroboros_auto_open_from_existing_thread_requests_sibling_thread(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)

    status = workflow.start(
        goal="Open sibling task thread",
        origin_platform="discord",
        origin_channel_id="parent-channel",
        origin_thread_id="source-thread",
        origin_message_id="message-1",
        auto_open_thread=True,
    )

    run_id = status["run_id"]
    handoff = json.loads((tmp_path / "data" / "houroboros" / run_id / "thread_handoff.json").read_text(encoding="utf-8"))
    assert status["origin"]["thread"]["state"] == "pending"
    assert status["origin"]["thread"]["thread_id"] is None
    assert handoff["request"]["parent_channel_id"] == "parent-channel"
    assert handoff["request"]["source_origin_thread_id"] == "source-thread"
    assert handoff["request"]["reuse_current_thread"] is False



def test_houroboros_redacts_secret_like_turns_before_artifacts(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Protect token=abc123456", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]

    workflow.turn(run_id, "Scope: use api_key=sk-test-secret")

    run_dir = tmp_path / "data" / "houroboros" / run_id
    combined = "\n".join(path.read_text(encoding="utf-8") for path in run_dir.glob("*.json*") if path.is_file())
    assert "abc123456" not in combined
    assert "sk-test-secret" not in combined
    assert "[REDACTED]" in combined


def test_houroboros_rejects_path_traversal_run_id(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)

    try:
        workflow.status("../escape")
    except ValueError as exc:
        assert "Invalid houroboros run_id" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("path traversal run_id must be rejected before file access")



def test_houroboros_discord_card_contract_v2_components_and_custom_ids(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(
        goal="Render Discord buttons safely",
        origin_platform="discord",
        origin_channel_id="parent",
        auto_open_thread=True,
    )
    run_id = started["run_id"]
    cards_path = tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl"
    card = json.loads(cards_path.read_text(encoding="utf-8").splitlines()[-1])

    assert card["contract_version"] == 2
    assert card["card_id"] == f"hooo-interview:{run_id}"
    assert card["card_revision"] == 1
    assert card["idempotency_key"] == f"hooo:discord-card:{run_id}:1"
    assert card["target"]["platform"] == "discord"
    assert card["interaction_policy"]["reject_stale_revision"] is True
    assert card["interaction_policy"]["do_not_bypass_ambiguity_gate"] is True
    assert card["card"]["proposal_card"]["dimension"] == "scope"
    components = card["card"]["components"]
    assert [component["action"] for component in components] == ["select_proposal", "select_proposal", "select_proposal", "other_opinion"]
    assert len(_proposal_components(card)) == 3
    assert all(component["type"] == "button" for component in components)
    assert all(component["custom_id"].startswith("hooo:v2:") for component in components)
    assert all(len(component["custom_id"]) <= 100 for component in components)
    for option_id, component in zip(["a", "b", "c"], _proposal_components(card), strict=True):
        assert f":dscope:o{option_id}" in component["custom_id"]


def test_houroboros_interaction_reducer_continue_writes_new_card_and_rejects_stale(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Continue via button", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]

    continued = workflow.handle_interaction(run_id, "continue_interview", card_revision=1, origin_channel_id="parent", actor_id="u1")
    assert continued["interaction"]["action"] == "continue_interview"
    assert continued["interaction"]["card_revision"] == 2
    assert continued["phase"] == "interviewing"
    log_path = tmp_path / "data" / "houroboros" / run_id / "interaction_log.jsonl"
    assert "continue_interview" in log_path.read_text(encoding="utf-8")

    try:
        workflow.handle_interaction(run_id, "continue_interview", card_revision=1, origin_channel_id="parent")
    except ValueError as exc:
        assert "Stale or unknown HOOO interaction card revision" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("stale Discord button click must be rejected")


def test_houroboros_interaction_propose_seed_rechecks_ambiguity_gate(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Do not seed from unsafe button", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]

    try:
        workflow.handle_interaction(run_id, "propose_seed", card_revision=1, origin_channel_id="parent")
    except ValueError as exc:
        assert "ambiguity" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("propose_seed button must not bypass ambiguity gate")

    _make_seed_ready(workflow, run_id)
    latest_revision = len((tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl").read_text(encoding="utf-8").splitlines())
    seeded = workflow.handle_interaction(run_id, "propose_seed", card_revision=latest_revision, origin_channel_id="parent")
    assert seeded["phase"] == "seeded"
    assert seeded["interaction"]["gate_rechecked"] is True


def test_houroboros_interaction_custom_id_validation_and_origin_mismatch(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Validate custom id", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]
    card = json.loads((tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    custom_id = card["card"]["components"][0]["custom_id"]

    result = workflow.handle_interaction(run_id, "", custom_id=custom_id, origin_channel_id="parent")
    assert result["interaction"]["action"] == "select_proposal"
    assert result["interaction"]["dimension"] == "scope"

    try:
        workflow.handle_interaction(run_id, "cancel", custom_id=custom_id, origin_channel_id="parent")
    except ValueError as exc:
        assert "action/custom_id mismatch" in str(exc) or "Stale" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("custom_id action mismatch must be rejected")

    latest_revision = len((tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl").read_text(encoding="utf-8").splitlines())
    try:
        workflow.handle_interaction(run_id, "continue_interview", card_revision=latest_revision + 1, origin_channel_id="parent")
    except ValueError as exc:
        assert "Stale or unknown HOOO interaction card revision" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("future card revision must be rejected")

    try:
        workflow.handle_interaction(run_id, "continue_interview", origin_channel_id="parent")
    except ValueError as exc:
        assert "card_revision is required" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("interaction without revision/custom_id must be rejected")

    try:
        workflow.handle_interaction(run_id, "select_proposal", custom_id=f"hooo:v2:select_proposal:other-run:r1:dscope:oa", origin_channel_id="parent")
    except ValueError as exc:
        assert "run_id mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("custom_id run mismatch must be rejected")

    latest_revision = len((tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl").read_text(encoding="utf-8").splitlines())
    try:
        workflow.handle_interaction(run_id, "continue_interview", card_revision=latest_revision, origin_channel_id="wrong-parent")
    except ValueError as exc:
        assert "channel mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("interaction channel mismatch must be rejected")

    try:
        workflow.handle_interaction(run_id, "continue_interview", card_revision=latest_revision)
    except ValueError as exc:
        assert "channel mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing interaction channel must be rejected when run has a channel")



def test_houroboros_cli_interact_reducer_emits_json(tmp_path: Path, capsys):
    config_file = _write_config(tmp_path)
    assert main([
        "hooo", "start", "--config", str(config_file), "--goal", "CLI button reducer", "--origin-platform", "discord", "--origin-channel-id", "parent"
    ]) == 0
    started = _payload(capsys)
    run_id = started["run_id"]

    assert main([
        "hooo", "interact", "--config", str(config_file), "--run-id", run_id, "--action", "continue_interview", "--card-revision", "1", "--origin-channel-id", "parent", "--actor-id", "u1"
    ]) == 0
    payload = _payload(capsys)
    assert payload["interaction"]["action"] == "continue_interview"
    assert payload["interaction"]["card_revision"] == 2

    assert main([
        "hooo", "interact", "--config", str(config_file), "--run-id", run_id, "--action", "propose_seed", "--card-revision", "2", "--origin-channel-id", "parent"
    ]) == 1
    error_payload = _payload(capsys)
    assert error_payload["ok"] is False
    assert "ambiguity" in error_payload["error"]



def test_houroboros_interaction_reducer_phase_and_thread_guards(tmp_path: Path):
    config_file = _write_config(tmp_path)
    workflow = HouroborosWorkflow.from_config_path(config_file)
    started = workflow.start(goal="Guard reducer phase", origin_platform="discord", origin_channel_id="parent")
    run_id = started["run_id"]

    try:
        workflow.handle_interaction(run_id, "continue_interview", card_revision=1, origin_channel_id="parent", origin_thread_id="unexpected-thread")
    except ValueError as exc:
        assert "thread mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unexpected thread id must be rejected when run is not bound to a thread")

    thread_bound = workflow.start(goal="Thread bound reducer", origin_platform="discord", origin_channel_id="parent", origin_thread_id="thread-1")
    thread_run_id = thread_bound["run_id"]
    try:
        workflow.handle_interaction(thread_run_id, "continue_interview", card_revision=1, origin_channel_id="parent")
    except ValueError as exc:
        assert "thread mismatch" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing interaction thread must be rejected when run has a thread")

    _make_seed_ready(workflow, run_id)
    latest_revision = len((tmp_path / "data" / "houroboros" / run_id / "discord_cards.jsonl").read_text(encoding="utf-8").splitlines())
    workflow.handle_interaction(run_id, "propose_seed", card_revision=latest_revision, origin_channel_id="parent")

    try:
        workflow.handle_interaction(run_id, "continue_interview", card_revision=latest_revision, origin_channel_id="parent")
    except ValueError as exc:
        assert "Invalid HOOO interaction continue_interview from phase seeded" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("continue_interview must be rejected after seeding")

    try:
        workflow.handle_interaction(run_id, "cancel", card_revision=latest_revision, origin_channel_id="parent")
    except ValueError as exc:
        assert "Invalid HOOO interaction cancel from phase seeded" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("cancel must be rejected after seeding")
