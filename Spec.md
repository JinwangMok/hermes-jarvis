# Jinwang Jarvis MVP Execution Spec

## Document role
This file is the execution contract for completing the remaining MVP features of `jinwang-jarvis` end-to-end.

## Goal
Finish the personal mail/calendar intelligence MVP so it can: collect mail + calendar data, classify messages, generate recommendation-only proposals and digests, record allow/reject feedback, run progressive backfill windows, and produce a weekly review artifact.

## Current live baseline
Already implemented and verified before this run:
- workspace bootstrap + SQLite schema
- mail collector (`collect-mail`)
- calendar collector (`collect-calendar`)
- sender resolution + transparent classifier (`classify-messages`)

## Remaining MVP scope
1. Proposal engine with calendar dedup + persisted `action_signals` and `event_proposals`
2. Digest generation artifact from the proposal/classification state
3. Feedback recording (`allow` / `reject`) with reason capture and persistence
4. Weekly review artifact summarizing obligations and unresolved items
5. Progressive backfill runner that records windows in `backfill_runs`
6. CLI/bin/docs/test coverage for all remaining flows

## Product rules
- Never auto-create calendar events.
- Proposals remain recommendation-only.
- Feedback must persist rejection reasons and influence future suppression/scoring.
- Advisor mail must remain high priority.
- The project stays Hermes-core-independent and CLI-driven.

## Execution phases
### Phase A — Proposal and digest pipeline
- Implement proposal extraction/scoring/dedup/persistence
- Emit `data/proposals/*.json`
- Emit `data/digests/*.md`

### Phase B — Feedback + learning loop
- Implement feedback recorder CLI and file output
- Use accumulated rejection reasons in proposal suppression/scoring

### Phase C — Weekly review + backfill
- Implement weekly review artifact generator
- Implement progressive backfill runner with checkpointed windows

### Phase D — Final integration verification
- Run full test suite
- Run real CLI commands against current workspace state
- Confirm files, DB rows, and checkpoints update correctly

## Acceptance criteria
- `pytest -q` passes
- All planned CLI entrypoints exist and run
- Real-state run creates at least one digest artifact
- Proposal generation writes DB rows + proposal artifact without duplicating existing calendar events
- Feedback recording updates `proposal_feedback` and proposal status
- Weekly review writes artifact and summarizes current state
- Backfill runner writes `backfill_runs` records

## Progress log
- 2026-04-19: Spec created for remaining MVP completion.
