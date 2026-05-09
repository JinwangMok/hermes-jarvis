# Minerva process-gate architecture (2026-05-09)

## Trigger
Use this reference when Jinwang frames Boramae/Minerva/ZeusOS roles or asks to push the ZeusOS rearchitecture toward the full D target: personal assistant surface + platform + orchestration OS.

## User-corrected To-Be
- BoramaeBot is the Discord-facing conversational surface with Jinwang.
- Minerva is the interpreting and commanding core: it translates conversation into directed work over ZeusOS + the current Hermes platform.
- ZeusOS is the template-based, extensible, declarative Agent OS platform underneath.
- Hermes is the current runtime/gateway substrate, but not the permanent conceptual boundary.

## Canonical Minerva loop
Every Minerva-driven workflow should model this sequence explicitly:

1. `user_question`
2. `idea_direction_explore`
3. `consensus_convergence`
4. `clarifying`
5. `planning`
6. `critic_for_plan`
7. `workload_parsing_workflow_designing`
8. `execute`
9. `review_align_to_goal`
10. `recognize_missing_gap`
11. `evolving`

Each phase should carry:
- at least two self-questions
- an Agree prompt: what evidence supports advancement?
- a Disagree prompt: what concern, ambiguity, or risk blocks advancement?
- quantitative gate scores/thresholds
- an explicit next phase
- a failure route when relevant

Important loopback: if `critic_for_plan` fails, route back to `idea_direction_explore`, not execution.

Execution gate: `execute` must require parallel/safe/self-heal dimensions before advancing to review.

## Implementation pattern proven in ZeusOS
Bounded leaves used successfully:
1. Create a pure, side-effect-free process model (`src/zeus_os/minerva_process.py`) with immutable phase/gate data and `evaluate_phase_gate`.
2. Add tests for phase order, self-questions, agree/disagree prompts, quantitative blocking, critic loopback, execute requirements, and side-effect-free results.
3. Connect the model to HOOO seed metadata only after the pure model is committed; add `minerva_process_gate` to `seed.json` as metadata, not live runtime wiring.
4. Keep Discord/gateway/systemd/cron untouched unless separately approved.

## Verification pattern
- TDD first: fail on missing module or missing seed metadata.
- Targeted tests: `tests/test_minerva_process.py`, `tests/test_houroboros.py`.
- Full suite before commit when in ZeusOS repo.
- Independent review of staged diff before commit.

## Reporting style
Explain the operational meaning first: "Boramae talks; Minerva commands; ZeusOS/Hermes executes." Then list commit/test evidence.
