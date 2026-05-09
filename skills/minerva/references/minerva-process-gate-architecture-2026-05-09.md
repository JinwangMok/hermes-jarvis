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
1. Create a pure, side-effect-free process model (`src/zeus_os/minerva_process.py`) with immutable phase/gate data, model version, phase contract export, `evaluate_phase_gate`, and card/contract helpers.
2. Add tests for phase order, self-questions, agree/disagree prompts, quantitative blocking, critic loopback, execute requirements, and side-effect-free results.
3. Expose the deterministic contract through read-only CLI before relying on it operationally:
   - `zeus-os minerva-process-contract` returns the model version, ordered phases, prompts, thresholds, and transitions.
   - `zeus-os minerva-phase-gate --phase <id> --score dimension=value ...` returns a deterministic gate card and rejects malformed scores with JSON `{ok:false}` plus exit 1.
4. Connect the model to Minerva seed metadata after the pure model/CLI are verified; add `minerva_process_gate` to `seed.json` as evidence, not live Hermes/gateway wiring.
5. Make Minerva seed create a concrete `workflow_design.json` from structured interview state and acceptance criteria. The artifact should include the `workload_parsing_workflow_designing` gate, planned work items, deterministic workflow sequence, executor, parallelization policy, safety policy, and self-heal policy.
6. Make `run()` consume `workflow_design.json` or the embedded seed copy before execution. If `phase_gate.gate.allowed` is not true, block execution with an error naming failed dimensions and route back to planning/critic rather than running placeholder or worker execution.
7. Keep Discord/gateway/systemd/cron untouched unless separately approved. Treat these Minerva/Minerva gate changes as repo/test/temp-workspace side effects only until an explicit live-wiring gate.

## Verification pattern
- TDD first: fail on missing module, missing CLI command, missing seed metadata, missing `workflow_design`, or missing execution block on failed gate.
- Targeted tests: `tests/test_minerva_process.py`, `tests/test_minerva_process_cli.py`, `tests/test_minerva.py`.
- CLI smoke examples:
  - `PYTHONPATH=src python3 -m zeus_os.cli minerva-process-contract` and assert `model_version == minerva.process-gate/v1` plus 11 phases.
  - `PYTHONPATH=src python3 -m zeus_os.cli minerva-phase-gate --phase execute --score alignment=1 --score consensus=1 --score clarity=1 --score safety=1 --score evidence=1 --score parallel=1 --score safe=1 --score self_heal=1` and assert next phase `review_align_to_goal`.
  - Start/turn/seed/run in a temporary Minerva workspace and assert `workflow_design.json` exists, the gate is allowed, and execution writes no external mutations.
- Full suite before commit when in ZeusOS repo.
- Independent review of staged diff before commit.
- Commit only after implementation + targeted verification + smoke/application proof + reviewer PASS; Jinwang’s stated completion bar is implementation, verification, and application, not design-only.

## Reporting style
Explain the operational meaning first: "Boramae talks; Minerva commands; ZeusOS/Hermes executes." Then list commit/test evidence.
