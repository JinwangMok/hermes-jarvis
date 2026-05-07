# Phase 1.0 Gate — Rename-Blocker Audit

**Substage:** `01-rename-blocker-audit`  
**Mode:** read-only audit artifact generation, no production source edits.  
**Controller rule:** external contractor + Hermes MoA must align >=95% before next substage.

## Required deliverables

| Deliverable | Path | Status |
|---|---|---|
| Active automation inventory | `active-automation-inventory.md` | present |
| Hermes cron inventory | `hermes-cron-inventory.md` | present |
| CLI parser drift report | `cli-parser-drift-report.md` | present |
| Hardcoded path inventory | `hardcoded-path-inventory.md` | present |
| Wiki path dependency map | `wiki-path-dependency-map.md` | present |
| Import dependency graph | `import-dependency-graph.md` | present |
| Formal AS-IS → TO-BE matrix | `as-is-to-be-matrix.md` | present |
| Phase 1 acceptance test plan | `phase1-acceptance-test-plan.md` | present |
| Zeus test evidence | `zeus-tests.txt` | present, `79 passed` |

## Score

| Dimension | Weight | Score | Weighted | Evidence |
|---|---:|---:|---:|---|
| Scope compliance | 30 | 100 | 30.00 | Only `orchestration/` artifacts were written |
| Invariant preservation | 25 | 100 | 25.00 | Hermes/source/systemd/external repos untouched; no rename |
| Test/proof readiness | 20 | 95 | 19.00 | `tests/test_zeus_*.py`: 79 passed; Phase 1 tests specified but not yet implemented |
| Artifact provenance | 15 | 100 | 15.00 | Kimi/GLM/controller artifacts and audit outputs exist |
| Documentation consistency | 10 | 95 | 9.50 | Matrix follows compatibility-first contract; notes remaining ambiguity |

**FINAL_PHASE_1_0_GATE_SCORE: 98.5/100 — PASS.**

## Allowed next substage

Only the following may proceed:

> **Phase 1.1 — CLI parser drift/parity cleanup**

Reason: it is the smallest local code cleanup, fully testable, does not touch live automation, does not rename repo/import/systemd/wiki paths, and directly addresses a controller-verified blocker.

## Still blocked

- `zeusos` CLI alias or import shim.
- Repo/package/import namespace rename.
- systemd/timer/gateway/Hermes profile changes.
- Wiki path movement or generated writer migration.
- External repo mutation/vendoring.
- Live Discord/mail/calendar/A2A posting.
- Browser recipe runtime/helper mutation.
- Push/publication.

## Gate condition for Phase 1.1

Phase 1.1 must produce:
1. A code diff limited to CLI parser parity/dedupe and tests.
2. Passing targeted Zeus CLI tests.
3. Passing `tests/test_zeus_*.py`.
4. `git diff --name-only` showing no Hermes/systemd/wiki/external repo changes.
5. A new `02-cli-parser-drift/gate.md` with score >=95.
