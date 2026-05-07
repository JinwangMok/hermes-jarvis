# Phase 1 Acceptance Test Plan

**Purpose:** define the tests required before and after rename-blocker cleanup. No code cleanup may start unless this plan and `gate.md` pass >=95.

## Phase 1.1 — CLI parser drift / parity

Acceptance criteria:
- Existing invocation remains valid: `python -m jinwang_jarvis.cli zeus ...`.
- Top-level Jarvis CLI delegates Zeus subcommands to `jinwang_jarvis.zeus_os.cli` or has an explicit parity test.
- Zeus subcommand tree (`init`, `doctor`, `task`, `agent`, `queue`, `worker`, `boardroom`, `a2a`, `painter`) cannot drift silently.
- No additive `zeusos` alias yet.

Required tests:
- `tests/test_zeus_cli.py::test_top_level_zeus_parser_matches_zeus_os_parser`
- `tests/test_zeus_cli.py::test_top_level_zeus_unknown_subcommand_fails_like_standalone`
- Existing `tests/test_zeus_cli.py` remains green.

Side-effect class: `repo_write` only.
Gate: score >=95; no Hermes/systemd/config/external repo diffs.

## Phase 1.2 — Workspace path hardcoding cleanup

Acceptance criteria:
- Runtime source under `src/jinwang_jarvis/zeus_os` has no `/home/jinwang/workspace/jinwang-jarvis` assumption.
- Non-Zeus tests that deliberately assert local default paths are classified as compatibility tests, not rename blockers.
- Any changed defaults remain backward-compatible with `config/pipeline.local.yaml`.
- systemd unit files and Hermes cron workdirs are not modified in this phase.

Required tests:
- `tests/test_config.py` updated only if behavior intentionally changes.
- New audit test or script proving Zeus source has no absolute personal workspace path.
- Existing `tests/test_zeus_*.py` green.

Side-effect class: `repo_write` only.
Gate: score >=95; live automation untouched.

## Phase 1.3 — Styled voice sample path configization

Acceptance criteria:
- Existing `--library-dir` behavior remains valid.
- Default sample path can resolve from workspace/config rather than hardcoded `~/workspace/jinwang-jarvis` when a workspace is supplied.
- Existing plugin/gateway behavior is not restarted or reconfigured.

Required tests:
- `tests/test_styled_voice_samples.py` covers explicit library dir.
- Add default-path test with temp workspace/config if code changes.

Side-effect class: `repo_write` only.
Gate: score >=95; no gateway/plugin restart.

## Phase 1.4 — Approval/gate ledger baseline

Acceptance criteria:
- Side-effect classes are documented in a controller artifact.
- Unknown live side effects fail closed.
- Commit/push/publication/gateway/systemd/external repo/write actions are separated.

Required tests/artifacts:
- `orchestration/.../gate.md` per substage.
- Future code may add approval engine tests, but Phase 1.4 may remain docs/artifact-only.

## Always-run verification

```bash
PYTHONPATH=src python -m pytest tests/test_zeus_*.py -q
PYTHONPATH=src python -m pytest tests/test_config.py tests/test_styled_voice_samples.py -q  # when affected
PYTHONPATH=src python -m pytest -q  # before commit if code changed materially
```

## Auto-fail rules

- Any Hermes source/config/gateway/systemd change without explicit `gateway_systemd` approval.
- Any wiki `raw/` rewrite or generated-path movement.
- Any external repo mutation or vendoring.
- Any live Discord/mail/calendar post.
- Any credential access beyond existing read-only inventory.
- Any test skip/delete used to make the gate pass.
