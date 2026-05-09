from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from zeus_os.minerva_process import (
    CANONICAL_PHASE_IDS,
    DIMENSIONS,
    MODEL_VERSION,
    PHASES,
    evaluate_phase_gate,
    get_phase,
    phase_gate_card,
    process_contract,
)


EXPECTED_PHASE_IDS = [
    "user_question",
    "idea_direction_explore",
    "consensus_convergence",
    "clarifying",
    "planning",
    "critic_for_plan",
    "workload_parsing_workflow_designing",
    "execute",
    "review_align_to_goal",
    "recognize_missing_gap",
    "evolving",
]


def passing_scores(**overrides: float) -> dict[str, float]:
    scores = {dimension: 1.0 for dimension in DIMENSIONS}
    scores.update(overrides)
    return scores


def test_canonical_phase_order_exactly_matches_user_sequence_with_stable_ids() -> None:
    assert CANONICAL_PHASE_IDS == tuple(EXPECTED_PHASE_IDS)
    assert tuple(phase.id for phase in PHASES) == tuple(EXPECTED_PHASE_IDS)


def test_every_phase_has_self_questions_and_agree_disagree_discussion_prompts() -> None:
    for phase in PHASES:
        assert len(phase.self_questions) >= 2, phase.id
        assert phase.discussion_prompts.agree, phase.id
        assert phase.discussion_prompts.disagree, phase.id
        assert "agree" in phase.discussion_prompts.agree.lower()
        assert "disagree" in phase.discussion_prompts.disagree.lower()


def test_evaluate_phase_gate_returns_quantitative_scores_and_blocks_low_core_dimensions() -> None:
    blocked = evaluate_phase_gate("clarifying", passing_scores(clarity=0.2))

    assert blocked["allowed"] is False
    assert blocked["phase_id"] == "clarifying"
    assert blocked["next_phase"] == "clarifying"
    assert blocked["scores"]["clarity"] == pytest.approx(0.2)
    assert blocked["thresholds"]["clarity"] > blocked["scores"]["clarity"]
    assert "clarity" in blocked["failed_dimensions"]

    for dimension in ("alignment", "consensus", "clarity", "safety", "evidence"):
        result = evaluate_phase_gate("planning", passing_scores(**{dimension: 0.0}))
        assert result["allowed"] is False
        assert dimension in result["failed_dimensions"]


def test_plan_critic_failed_gate_routes_back_to_idea_explore_not_execute() -> None:
    result = evaluate_phase_gate("critic_for_plan", passing_scores(evidence=0.1))

    assert result["allowed"] is False
    assert result["next_phase"] == "idea_direction_explore"
    assert result["next_phase"] != "execute"


def test_execute_requires_parallel_safe_self_heal_before_review() -> None:
    for dimension in ("parallel", "safe", "self_heal"):
        result = evaluate_phase_gate("execute", passing_scores(**{dimension: 0.0}))
        assert result["allowed"] is False
        assert dimension in result["failed_dimensions"]
        assert result["next_phase"] == "execute"

    allowed = evaluate_phase_gate("execute", passing_scores())
    assert allowed["allowed"] is True
    assert allowed["next_phase"] == "review_align_to_goal"


def test_process_contract_exports_deterministic_thresholds_and_prompts() -> None:
    contract = process_contract()

    assert contract["model_version"] == MODEL_VERSION
    assert [phase["id"] for phase in contract["phases"]] == EXPECTED_PHASE_IDS
    execute = next(phase for phase in contract["phases"] if phase["id"] == "execute")
    assert execute["thresholds"] == {
        "alignment": 0.75,
        "consensus": 0.65,
        "clarity": 0.70,
        "safety": 0.80,
        "evidence": 0.60,
        "parallel": 0.60,
        "safe": 0.85,
        "self_heal": 0.70,
    }
    assert execute["discussion_prompts"]["agree"].startswith("Agree:")
    assert execute["discussion_prompts"]["disagree"].startswith("Disagree:")


def test_phase_gate_card_combines_contract_and_quantitative_decision() -> None:
    card = phase_gate_card("critic_for_plan", passing_scores(evidence=0.1))

    assert card["model_version"] == MODEL_VERSION
    assert card["phase"]["id"] == "critic_for_plan"
    assert card["phase"]["label"] == "Critic for Plan"
    assert len(card["phase"]["self_questions"]) >= 2
    assert card["discussion"]["agree"].startswith("Agree:")
    assert card["discussion"]["disagree"].startswith("Disagree:")
    assert card["gate"]["allowed"] is False
    assert card["gate"]["next_phase"] == "idea_direction_explore"


def test_all_gates_are_side_effect_free_data_objects_and_dicts() -> None:
    phase = get_phase("planning")
    assert is_dataclass(phase)
    with pytest.raises(FrozenInstanceError):
        phase.id = "mutated"  # type: ignore[misc]

    scores = passing_scores()
    result = evaluate_phase_gate("planning", scores)
    scores["alignment"] = 0.0

    assert isinstance(result, dict)
    assert result["scores"]["alignment"] == pytest.approx(1.0)
    assert result["allowed"] is True
    assert result["next_phase"] == "critic_for_plan"
