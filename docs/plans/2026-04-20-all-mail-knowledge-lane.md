# All Mail Knowledge Lane + Daily Intelligence Plan

> For Hermes: implement this plan end-to-end without stopping before verification and the final monthly report.

**Goal:** Add an `All Mail`-based knowledge lane that preserves operational precision while expanding long-term news/opportunity memory for Jarvis.

**Architecture:** Keep the existing operational lane (`INBOX + sent`) unchanged for proposals/approval loops. Add a separate `knowledge_messages` store fed from Gmail `All Mail`/archive-like folders, then generate category-based daily intelligence artifacts and wiki notes from that store.

**Tech Stack:** Python, SQLite, Himalaya CLI, existing Jarvis CLI/runtime/wiki pipeline.

---

## Scope
1. Add DB schema for knowledge-lane mail.
2. Add collector/backfill for All Mail-like folders.
3. Add rule-based category/opportunity scoring.
4. Add daily intelligence report artifact + wiki notes.
5. Run collector/backfill for the current 36-month horizon.
6. Generate a monthly 3-year report from the updated wiki/data.

## Guardrails
- Do not break existing proposal/approval behavior.
- Keep operational lane on `INBOX + sent`.
- Use the new lane for history/news/opportunity memory.
- Prefer simple rule-based categorization first; verify with tests.
