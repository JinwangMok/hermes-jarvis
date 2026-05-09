# Jarvis-native Minerva QA Result

## 1. Verdict: PASS_WITH_NOTES

The implementation is additive, locally testable, and meets the MVP shape of Interview -> Seed -> Execute -> Evaluate -> Evolve with status/export and drift artifacts. I found no BLOCKER issues and no evidence of Hermes/source/systemd/cron/external-service side effects. The main pre-merge concern is an IMPORTANT workflow integrity gap: phase order is not enforced, so a run can evolve without execution or evaluation evidence.

## 2. Tests run: commands and outputs summarized

- `PYTHONPATH=src pytest -q tests/test_minerva.py` -> `4 passed in 0.78s`.
- `PYTHONPATH=src pytest -q tests/test_minerva.py tests/test_cli.py tests/test_bootstrap.py` -> `19 passed in 66.57s`.
- `PYTHONPATH=src pytest -q` -> `189 passed, 1 failed in 141.64s`. The failure is `tests/test_config.py::test_load_pipeline_config_exposes_reproducible_workspace_metadata`, which expects `/home/jinwang/workspace/jinwang-jarvis` while this worktree resolves `config/pipeline.yaml` to `/home/jinwang/workspace/jinwang-jarvis-minerva-worktree`. This appears to be an existing worktree/config-path mismatch, not caused by the Minerva changes.
- LSP diagnostics on `src/jinwang_jarvis/minerva.py`, `src/jinwang_jarvis/cli.py`, and `tests/test_minerva.py` -> no diagnostics found.
- `PYTHONPATH=src python -m compileall -q src/jinwang_jarvis tests/test_minerva.py` -> exit 0, no output.
- Custom AST security scan of `src/jinwang_jarvis/minerva.py` and `src/jinwang_jarvis/cli.py` for subprocess/network/shell/eval patterns -> `{'dangerous_patterns': [], 'ok': True}`.
- `python -m bandit -q src/jinwang_jarvis/minerva.py src/jinwang_jarvis/cli.py` -> not runnable in this environment: `No module named bandit`.
- Isolated manual CLI workflow under `/tmp/opencode/minerva-qa-manual-local` using `minerva start -> turn -> seed -> run -> evaluate -> evolve -> status -> export` -> all commands exited 0; final phase `evolved`; Discord origin metadata preserved; 8 artifacts produced under the temp workspace; export returned run/status/interview/seed/artifact texts.
- Concrete phase-order repro under `/tmp/opencode/minerva-qa-order-repro` -> `minerva start -> seed -> evolve` exited 0 and set phase `evolved` without `execution_log.md`, `evaluation.md`, or `drift.md`.

## 3. Security/side-effect review

No side effects beyond configured Jarvis workspace state/artifacts were observed during QA. Manual CLI runs wrote only under `/tmp/opencode/...` workspaces. `git status --short` after testing showed the expected implementation files plus this QA artifact directory; there were no changes under Hermes source, `~/.hermes`, systemd, cron, secrets, or external-service configuration.

The new `minerva.py` path uses SQLite parameter binding for run lookup/update and generates run IDs internally from goal + timestamp. Public methods validate `run_id` by loading an existing DB row before artifact access. The new workflow code imports no subprocess, network, shell, or home-directory APIs. The CLI namespace is additive and does not alter existing command handlers.

## 4. Functional workflow review

The happy-path workflow is usable: `start` creates a run with origin metadata, `turn` records interview messages, `seed` writes immutable v1 seed artifacts, `run` writes deterministic execution evidence, `evaluate` writes `evaluation.md` and `drift.md`, `evolve` writes an evolution proposal, `status` exposes phase/artifacts/origin/latest drift, and `export` returns a complete JSON bundle.

The harness is not interview-only. However, workflow integrity is currently soft: methods do not enforce legal transitions. The clearest concrete bug is that `evolve` can run immediately after `seed`, skipping execution and evaluation while still marking the run `evolved`. Also, `run` is a deterministic placeholder that manufactures PASS evidence by echoing acceptance criteria into the execution log; this is acceptable only if the MVP explicitly treats Execute as a side-effect-free evidence placeholder.

## 5. Regression review

The new CLI command is namespaced under `minerva` with alias `minerva`, and targeted CLI/bootstrap tests pass. Existing high-risk commands such as bootstrap and older CLI flows were not changed except for importing `MinervaWorkflow` and adding the new parser branch. The full suite has one config-path failure that predates or sits outside this implementation’s scope; it should not block this specific branch unless the merge policy requires a fully green suite in this worktree.

## 6. Test coverage critique

The added tests prove the happy path, basic CLI JSON output, seed immutability, missing-run behavior, and docs existence. They do not yet cover illegal phase transitions, `minerva` alias execution, CLI error behavior for missing/unknown runs, evaluation before execution, append-turn behavior after seed/evolve, corrupted JSONL/seed files, concurrent duplicate starts, or export/status behavior when artifacts are partially missing. The tests also accept the placeholder execution model without asserting that evaluation reflects real execution evidence.

## 7. Findings table: severity, file/area, evidence, recommendation

| Severity | File/area | Evidence | Recommendation |
| --- | --- | --- | --- |
| IMPORTANT | `src/jinwang_jarvis/minerva.py` phase/state machine | Repro: create isolated config, run `minerva start --config /tmp/opencode/minerva-qa-order-repro/pipeline.yaml --goal "Repro missing phase gating"`, then `minerva seed --config ... --run-id <id>`, then `minerva evolve --config ... --run-id <id>`. Expected: reject because execution/evaluation/drift are missing. Actual: exit 0, phase becomes `evolved`, artifacts only include `origin.json`, `seed.json`, `seed.md`, `evolution.md`. | Enforce allowed phase transitions. Require `evolve` to follow a completed `evaluate`, require `evaluate` to follow `run`, and return deterministic CLI errors for invalid order. Add tests for each rejected transition. |
| IMPORTANT | `tests/test_minerva.py` coverage | Tests cover only the normal ordered path and docs existence. No tests assert rejection of skipped phases, `minerva` alias behavior, CLI error codes, partial/missing artifacts, or post-seed interview mutation semantics. | Add negative and edge-case tests before merge if workflow integrity is a product requirement. At minimum, cover skipped `run/evaluate`, unknown run via CLI, and direct `minerva` alias invocation. |
| PHASE2 | Execute/Evaluate product semantics | `run()` writes `PASS evidence recorded for: <criterion>` for every seed criterion, and `evaluate()` passes when criterion text is present in that generated log. This proves artifact plumbing but not real task execution. | Keep for MVP only if explicitly documented as placeholder execution. For phase 2, introduce an explicit executor contract and evidence model that cannot self-certify acceptance by string echo alone. |
| PHASE2 | Operator/Discord continuity | Status/export include platform/channel/thread, phase, artifacts, and drift. They do not include Discord message ID, jump URL, actor/user ID, resume command hints, or a concise next-action field. | Add richer origin/resume metadata when Hermes/Discord phase 2 needs thread continuity and operator handoff. |
| MINOR | Static scan tooling | Bandit is not installed in this environment, so external Bandit scan could not run. Custom AST scan and targeted greps found no dangerous patterns in changed workflow files. | Add Bandit (or equivalent) to CI/dev dependencies if Python security scanning is expected as a standard gate. |

## 8. Merge recommendation and required pre-merge fixes

Merge recommendation: PASS_WITH_NOTES. If this branch is intended as a side-effect-free MVP harness with placeholder execution, it is mergeable after accepting the known phase-transition risk. If the product contract requires strict workflow sequencing before merge, fix the IMPORTANT phase-order issue first.

Required pre-merge fixes: enforce phase transition guards if skipped execution/evaluation is unacceptable; add tests for invalid transitions. Non-blocking follow-ups: enrich Discord/operator resume metadata, replace placeholder execution/evaluation with a real evidence contract, and install a standard security scanner in the environment or CI.
