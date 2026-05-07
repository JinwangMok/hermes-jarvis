# ZeusOS End-to-End Gated Execution Plan

**Controller rule:** each stage/substage must have (1) local controller evidence, (2) external contractor or MoA review, and (3) score >=95 before proceeding.

## Stop lines

Stop and ask Jinwang before any:
- Hermes source/runtime/config/gateway/systemd restart or mutation
- external repo vendoring/mutation
- destructive canonical DB migration
- systemd/wiki/generated-path rename
- live helper patch promotion
- `zeusos` public alias that could imply rename completion

## Stage 00 — replay/gap audit

- Artifact: `00-controller/converged-gate-00.md`
- External inputs: Kimi/GLM/MoA audits under `00-replay-gap-audit-*`
- Status: PASS >=95
- Outcome: compatibility-first ZeusOS direction confirmed; missing items converted into gated execution.

## Stage 01 — rename-blocker audit

- Artifact: `01-rename-blocker-audit/gate.md`
- Status: PASS 98.5/100
- Allowed next: small repo-write cleanup only; no systemd/wiki/Hermes mutation.

## Stage 02 — CLI parser drift cleanup

- Artifact: `02-cli-parser-drift/gate.md`
- Status: PASS 99.8/100
- Scope: deduplicate Zeus parser registration; preserve `jinwang-jarvis zeus ...`.

## Stage 03 — path/styled-voice config cleanup

- Artifact: `03-path-styledvoice/gate.md`
- Status: PASS 97/100 after remediation
- Scope: remove hardcoded styled-voice personal workspace default; add audit test for Zeus source path hardcoding.

## Stage 04 — runtime deterministic skeleton

Prereqs:
- Stage 00-03 pass.
- No destructive DB migration.
Acceptance:
- SQLite schema/store/queue/worker fixture works in temp workspace.
- Deterministic worker can process a fake task once.
- Event log and artifact registry remain canonical; Discord/A2A/Markdown remain projections.
- External/MoA score >=95.

## Stage 05 — adapter manifest + browser recipe dry-run

Prereqs:
- Stage 04 pass.
- No external repo mutation/vendoring.
Acceptance:
- Adapter manifest schema exists.
- Browser recipe registry supports dry-run/proposal artifacts only.
- Helper patches remain proposals, not live promotion.
- External/MoA score >=95.

## Stage 06 — final verification/report/commit decision

Acceptance:
- Full relevant pytest suite passes.
- Git diff reviewed.
- Orchestration artifacts classified as commit/archive/delete.
- No stop-line violations.
- Final report includes passed gates and remaining blocked migrations.
