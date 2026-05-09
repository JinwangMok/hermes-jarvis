"""Pure Minerva process-gate model.

This module intentionally contains only immutable data definitions and pure
functions.  It does not read files, write files, call services, spawn processes,
or depend on live Hermes/Minerva runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


MODEL_VERSION = "minerva.process-gate/v1"


CANONICAL_PHASE_IDS: tuple[str, ...] = (
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
)

DIMENSIONS: tuple[str, ...] = (
    "alignment",
    "consensus",
    "clarity",
    "safety",
    "evidence",
    "parallel",
    "safe",
    "self_heal",
)

CORE_THRESHOLDS: Mapping[str, float] = MappingProxyType(
    {
        "alignment": 0.75,
        "consensus": 0.65,
        "clarity": 0.70,
        "safety": 0.80,
        "evidence": 0.60,
    }
)

EXECUTE_THRESHOLDS: Mapping[str, float] = MappingProxyType(
    {
        **dict(CORE_THRESHOLDS),
        "parallel": 0.60,
        "safe": 0.85,
        "self_heal": 0.70,
    }
)


@dataclass(frozen=True)
class DiscussionPrompts:
    """Agree/disagree prompts carried by each process phase."""

    agree: str
    disagree: str


@dataclass(frozen=True)
class Phase:
    """Immutable description of a canonical Minerva process phase."""

    id: str
    label: str
    self_questions: tuple[str, ...]
    discussion_prompts: DiscussionPrompts
    thresholds: Mapping[str, float]
    next_phase: str | None
    failure_next_phase: str | None = None


_BASE_DISCUSSION = DiscussionPrompts(
    agree="Agree: what evidence supports advancing from this phase?",
    disagree="Disagree: what concern, ambiguity, or risk blocks advancement?",
)


def _phase(
    phase_id: str,
    label: str,
    self_questions: tuple[str, ...],
    next_phase: str | None,
    thresholds: Mapping[str, float] = CORE_THRESHOLDS,
    failure_next_phase: str | None = None,
) -> Phase:
    return Phase(
        id=phase_id,
        label=label,
        self_questions=self_questions,
        discussion_prompts=_BASE_DISCUSSION,
        thresholds=MappingProxyType(dict(thresholds)),
        next_phase=next_phase,
        failure_next_phase=failure_next_phase,
    )


PHASES: tuple[Phase, ...] = (
    _phase(
        "user_question",
        "User Question",
        (
            "What did Jinwang explicitly ask or correct?",
            "What outcome would answer the user's question without overreaching?",
        ),
        "idea_direction_explore",
    ),
    _phase(
        "idea_direction_explore",
        "Idea/Direction Explore",
        (
            "What candidate interpretations or directions exist?",
            "Which useful existing Minerva/Hermes concepts should be kept conceptually?",
        ),
        "consensus_convergence",
    ),
    _phase(
        "consensus_convergence",
        "Consensus/Convergence",
        (
            "Which direction has the strongest shared support?",
            "What disagreement remains and how material is it?",
        ),
        "clarifying",
    ),
    _phase(
        "clarifying",
        "Clarifying",
        (
            "What must be clarified before planning safely?",
            "Can missing details be retrieved, assumed explicitly, or must they be asked?",
        ),
        "planning",
    ),
    _phase(
        "planning",
        "Planning",
        (
            "What minimal sequence of actions satisfies the bounded objective?",
            "What files, systems, or boundaries must not be touched?",
        ),
        "critic_for_plan",
    ),
    _phase(
        "critic_for_plan",
        "Critic for Plan",
        (
            "Where can the plan fail against goal, safety, evidence, or scope?",
            "Does the plan need to return to idea exploration before any execution?",
        ),
        "workload_parsing_workflow_designing",
        failure_next_phase="idea_direction_explore",
    ),
    _phase(
        "workload_parsing_workflow_designing",
        "Workload Parsing/Workflow Designing",
        (
            "How should work be split into parallel, sequential, and verification units?",
            "What safe rollback or self-heal route exists for each unit?",
        ),
        "execute",
    ),
    _phase(
        "execute",
        "Execute",
        (
            "Are actions parallel where independent and sequential where dependent?",
            "Are safe execution and self-heal mechanisms present before proceeding?",
        ),
        "review_align_to_goal",
        thresholds=EXECUTE_THRESHOLDS,
    ),
    _phase(
        "review_align_to_goal",
        "Review/Align to Goal",
        (
            "Does the result match the user's original goal and boundaries?",
            "What evidence verifies the result?",
        ),
        "recognize_missing_gap",
    ),
    _phase(
        "recognize_missing_gap",
        "Recognize Missing Gap",
        (
            "What gap remains between result and desired outcome?",
            "Is the gap acceptable, documented, or a reason to loop back?",
        ),
        "evolving",
    ),
    _phase(
        "evolving",
        "Evolving",
        (
            "What reusable learning should improve future Minerva orchestration?",
            "What should be preserved as data or documentation without side effects here?",
        ),
        None,
    ),
)

_PHASE_BY_ID: Mapping[str, Phase] = MappingProxyType({phase.id: phase for phase in PHASES})


def _phase_contract(phase: Phase) -> dict[str, object]:
    return {
        "id": phase.id,
        "label": phase.label,
        "self_questions": list(phase.self_questions),
        "discussion_prompts": {
            "agree": phase.discussion_prompts.agree,
            "disagree": phase.discussion_prompts.disagree,
        },
        "thresholds": dict(phase.thresholds),
        "next_phase": phase.next_phase,
        "failure_next_phase": phase.failure_next_phase,
        "self_justification": {
            "required": True,
            "questions": list(phase.self_questions),
            "thresholds": dict(phase.thresholds),
            "evidence_required": True,
            "discussion_mode": "agree_disagree",
        },
    }


def process_contract() -> dict[str, object]:
    """Return the deterministic Minerva process contract as plain data."""

    return {
        "model_version": MODEL_VERSION,
        "phase_ids": list(CANONICAL_PHASE_IDS),
        "self_justification": {
            "required_every_phase": True,
            "minimum_questions": 2,
            "quantitative_gate_required": True,
            "evidence_required": True,
            "discussion_mode": "agree_disagree",
        },
        "phases": [_phase_contract(phase) for phase in PHASES],
    }


def phase_gate_card(phase_id: str, scores: Mapping[str, float]) -> dict[str, object]:
    """Return display-ready phase contract plus quantitative gate decision."""

    phase = get_phase(phase_id)
    return {
        "model_version": MODEL_VERSION,
        "phase": {
            "id": phase.id,
            "label": phase.label,
            "self_questions": list(phase.self_questions),
        },
        "discussion": {
            "agree": phase.discussion_prompts.agree,
            "disagree": phase.discussion_prompts.disagree,
        },
        "gate": evaluate_phase_gate(phase.id, scores),
    }


def get_phase(phase_id: str) -> Phase:
    """Return the immutable phase description for *phase_id*."""

    try:
        return _PHASE_BY_ID[phase_id]
    except KeyError as exc:
        raise ValueError(f"unknown Minerva phase: {phase_id}") from exc


def evaluate_phase_gate(phase_id: str, scores: Mapping[str, float]) -> dict[str, object]:
    """Evaluate whether a phase may advance.

    Args:
        phase_id: Stable canonical phase identifier.
        scores: Quantitative 0.0-1.0 dimension scores. Only dimensions required
            by the phase thresholds are evaluated; extra scores are preserved.

    Returns:
        A fresh dictionary containing copied quantitative scores, thresholds,
        failed dimensions, an ``allowed`` boolean, and the routed ``next_phase``.
    """

    phase = get_phase(phase_id)
    copied_scores = {name: float(value) for name, value in scores.items()}
    thresholds = dict(phase.thresholds)
    failed_dimensions = [
        dimension
        for dimension, threshold in thresholds.items()
        if copied_scores.get(dimension, 0.0) < threshold
    ]
    allowed = not failed_dimensions
    if allowed:
        next_phase = phase.next_phase
    else:
        next_phase = phase.failure_next_phase or phase.id

    return {
        "phase_id": phase.id,
        "allowed": allowed,
        "scores": copied_scores,
        "thresholds": thresholds,
        "failed_dimensions": failed_dimensions,
        "next_phase": next_phase,
    }
