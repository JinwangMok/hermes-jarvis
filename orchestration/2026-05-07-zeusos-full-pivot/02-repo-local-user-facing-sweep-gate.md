# Stage 2 Gate — Repo-local user-facing ZeusOS sweep

## Scope
- Repo-local user-facing docs/help/report titles/generator metadata/User-Agent/systemd template names/plugin messages.
- No live `systemctl`, no Hermes gateway restart, no repo path rename, no package deletion.
- Allowed residuals until later stages: `src/jinwang_jarvis` implementation/imports, `/home/jinwang/workspace/jinwang-jarvis` live path, legacy health unit names/env fallback used only to disable old timers, plugin package dir names.

## Fixes completed
- Canonical CLI/help now reports `zeus-os`.
- Generated wiki writers now emit ZeusOS paths/generator/owner/tag/title metadata for active generated surfaces.
- Repo-local systemd templates renamed to `zeus-os-*`; live path remains current repo path until cutover.
- Direct CLI and installer disable legacy `jinwang-jarvis-hermes-health.*` before enabling `zeus-os-hermes-health.timer`.
- Styled-voice Discord plugin messages changed from Jarvis to ZeusOS.
- External/runtime User-Agents changed to ZeusOS names.
- Styled-voice env precedence changed to `ZEUSOS_*` primary with `JARVIS_*` compatibility fallback.
- Wiki semantic lint fixture updated to `queries/zeus-os-*` generated prefix.

## Verification
- `git diff --check`: PASS.
- Targeted tests after final fixes: `45 passed` and additional focused suites PASS.
- Full suite: `393 passed in 202.85s`.
- Final MoA review: PASS 96/100.
- Final adversarial review: PASS 96/100.

## Decision
**PASS — 96/100.**

Next allowed stage: Stage 3 Hermes skills/config/plugin pivot, no gateway restart until live recovery belt and systemd health cutover gate pass.
