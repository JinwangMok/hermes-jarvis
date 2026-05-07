# Phase 1.1 Gate — CLI Parser Drift Cleanup

**Substage:** `02-cli-parser-drift`  
**Mode:** limited repo write: CLI parser single-source cleanup + regression tests.  
**Allowed by:** `01-rename-blocker-audit/gate.md` score 98.5/100.

## Diff scope

Changed production/test files:

- `src/jinwang_jarvis/zeus_os/cli.py`
  - Added `populate_zeus_subparsers(subparsers)` as the single source of truth for Zeus subcommand registration.
  - Kept `build_zeus_parser()` public behavior; it now delegates to `populate_zeus_subparsers()`.
- `src/jinwang_jarvis/cli.py`
  - Removed duplicate ~100-line Zeus parser definition.
  - Top-level `jinwang-jarvis zeus ...` now calls `populate_zeus_subparsers()`.
- `tests/test_zeus_cli.py`
  - Added top-level-vs-standalone parser parity tests.
  - Strengthened parity comparison to include subcommand tree and argument-level action signatures.

No Hermes source/config, systemd units, wiki paths, external repos, gateway state, cron jobs, or live adapters were modified.

## External contractor / MoA review

- GLM external reviewer artifact: `../02-cli-parser-drift-glm-review/result.md`.
- GLM initially scored the first diff as PASS with one low-risk concern: parity test checked tree shape, not argument-level flags/defaults.
- Controller repaired that concern by replacing `_command_tree()` with `_parser_tree()` + `_action_signature()`, comparing option strings, dest, required, nargs, const, default, and choices recursively.

## Verification

```text
PYTHONPATH=src python -m pytest tests/test_zeus_cli.py -q
15 passed in 0.85s

PYTHONPATH=src python -m pytest tests/test_zeus_*.py -q
81 passed in 0.92s
```

## Score

| Dimension | Weight | Score | Weighted | Evidence |
|---|---:|---:|---:|---|
| Scope compliance | 30 | 100 | 30.00 | Only approved CLI parser/test files changed |
| Invariant preservation | 25 | 100 | 25.00 | Compatibility names preserved; no alias/rename/systemd/wiki/Hermes changes |
| Test/proof readiness | 20 | 100 | 20.00 | Targeted + all Zeus tests pass; argument-level parser parity covered |
| Artifact provenance | 15 | 100 | 15.00 | GLM review + controller gate artifacts exist |
| MoA/external alignment | 10 | 98 | 9.80 | External concern repaired; controller and GLM agree PASS |

**FINAL_PHASE_1_1_GATE_SCORE: 99.8/100 — PASS.**

## Allowed next substage

Proceed only to:

> **Phase 1.2 — workspace/path hardcoding cleanup audit-to-code slice**

Initial safe slice: classify absolute path references into:
1. test fixtures/assertions that intentionally preserve compatibility,
2. source defaults that can be config/workspace-root driven,
3. live automation files that must remain blocked until `gateway_systemd`/automation gate.

Do **not** touch systemd units, Hermes cron jobs, gateway config, wiki path movement, or `zeusos` aliases in Phase 1.2.
