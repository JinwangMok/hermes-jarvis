# Minerva Team Result

## Summary

Implemented a Jarvis-native Minerva workflow harness without changing Hermes source or external runtime configuration. The MVP provides an additive CLI namespace (`minerva`, alias `minerva`) and deterministic sidecar workflow state/artifacts under the configured Jarvis workspace.

The implemented conceptual flow is Interview -> Seed -> Execute -> Evaluate -> Evolve with Status/Drift visibility. Deep Interview-style UX is represented only as the interview/front-end crystallization phase; the core harness locks a seed, records deterministic execution evidence, evaluates evidence against acceptance criteria, and writes an evolution proposal without mutating the seed.

## Files changed

- `src/jinwang_jarvis/minerva.py` — new workflow state machine, SQLite run ledger, workspace artifact writer, immutable seed/evaluate/evolve/status/export behavior.
- `src/jinwang_jarvis/cli.py` — additive `minerva` namespace and `minerva` alias with start/turn/seed/run/evaluate/evolve/status/export commands.
- `tests/test_minerva.py` — focused tests for state machine phases, CLI JSON outputs, artifact creation, immutable seed behavior, status/export, and skill docs.
- `skills/minerva/SKILL.md` — Jarvis-owned external skill contract for `/minerva`.
- `skills/minerva/SKILL.md` — Jarvis-owned external skill contract for `/minerva`.
- `docs/minerva-workflow.md` — UX and safety model documentation.
- `orchestration/2026-05-02-minerva-team/result.md` — this delivery report.

## Workflow coverage

- Interview: `start` creates a run with Discord origin metadata; `turn` appends normalized interview turns to `data/minerva/<run_id>/interview.jsonl`.
- Seed: `seed` creates immutable v1 `seed.json` and `seed.md`; rerunning `seed` returns existing seed metadata and does not rewrite the seed.
- Run: `run` writes deterministic placeholder execution evidence to `execution_log.md`; it does not execute subprocesses, call APIs, or mutate external systems.
- Evaluate: `evaluate` compares seed acceptance criteria with recorded execution evidence and writes `evaluation.md` and `drift.md`.
- Evolve: `evolve` writes `evolution.md` as a proposal based on the immutable seed and latest evaluation/drift artifacts.
- Status/Export: `status` exposes phase, artifacts, origin metadata, and latest drift; `export` returns run metadata, interview entries, seed, status, and artifact texts as JSON.

## Tests run and outputs

- Targeted Minerva tests:
  - Command: `PYTHONPATH=src pytest -q tests/test_minerva.py`
  - Output: `4 passed in 0.88s`
- Python syntax/compile check:
  - Command: `PYTHONPATH=src python -m compileall -q src/jinwang_jarvis tests/test_minerva.py`
  - Output: exit code 0, no output.
- Manual CLI QA in isolated `/tmp/opencode/minerva-manual-qa` workspace:
  - `minerva start` produced phase `interviewing` with Discord origin metadata.
  - `minerva turn` created `interview.jsonl`.
  - `minerva seed` created `seed.json` and `seed.md` with `seed_version: 1`.
  - `minerva run` created `execution_log.md` and phase `running`.
  - `minerva evaluate` created `evaluation.md`/`drift.md`, phase `evaluated`, `passed: true`.
  - `minerva evolve` created `evolution.md`, phase `evolved`.
  - `minerva status` exposed phase, artifacts, origin, and drift.
  - `minerva export` returned run, status, interview, seed, and artifact texts as JSON.
- Targeted workflow + existing CLI/bootstrap regression set:
  - Command: `PYTHONPATH=src pytest -q tests/test_minerva.py tests/test_cli.py tests/test_bootstrap.py`
  - Output: `19 passed in 55.13s`
- Full suite:
  - Command: `PYTHONPATH=src pytest -q`
  - Output: `189 passed, 1 failed in 119.34s`
  - Failure: `tests/test_config.py::test_load_pipeline_config_exposes_reproducible_workspace_metadata` expects `config/pipeline.yaml` to resolve to `/home/jinwang/workspace/jinwang-jarvis`, but this worktree resolves it to `/home/jinwang/workspace/jinwang-jarvis-minerva-worktree`. This is a worktree/config path contract mismatch and is not caused by the Minerva implementation. I did not change `config/pipeline.yaml` because the user explicitly warned not to touch the main dirty worktree; all Minerva manual QA used an isolated temp config instead.

## Side-effect safety notes

- No Hermes source, `~/.hermes`, Hermes config, Hermes-owned skills, wiki raw files, systemd, cron, secrets, or external services were modified.
- Tests and manual QA use temporary workspace paths for generated Minerva state/artifacts.
- The harness stores state in `state/minerva.db` and artifacts in `data/minerva/<run_id>/` under the configured Jarvis workspace.
- The MVP `run` command records execution evidence only; it does not perform autonomous code execution.
- Seed semantics are immutable: v1 seed files are not silently rewritten; `evolve` writes an evolution proposal artifact instead.

## Remaining risks / phase 2 items

- Transition validation is intentionally minimal for MVP; phase 2 should reject illegal transitions with deterministic error payloads.
- `run` is a placeholder evidence recorder; real execution should be added only behind an explicit command/contract and must preserve side-effect boundaries.
- `evaluate` currently uses simple deterministic text matching between criteria and evidence; richer evaluators can be added later if they stay offline and reproducible.
- Concurrent workflow locking is not implemented; SQLite state is sufficient for current CLI-driven single-operator use.
- The full pytest suite still has one unrelated config path failure that should be resolved separately by deciding whether this worktree’s checked-in `config/pipeline.yaml` should point to the canonical main checkout or the active worktree.
