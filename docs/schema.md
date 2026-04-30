# Schema notes for jinwang-jarvis

## Runtime directories
- `data/snapshots/mail/`
- `data/snapshots/calendar/`
- `data/exports/`
- `data/proposals/`
- `data/digests/`
- `data/briefings/`
- `data/feedback/`
- `data/watchlists/`
- `state/`
- `state/locks/`
- `queries/jinwang-jarvis-memory/` in the wiki for hierarchical memory notes

## Core SQLite tables
- `messages`
- `sender_identities`
- `message_labels`
- `action_signals`
- `calendar_events`
- `event_proposals`
- `proposal_feedback`
- `backfill_runs`
- `message_watchlist`

## Operational FTS sidecar tables
These tables are rebuildable search indexes created only when SQLite FTS5 is available. `wiki-search-index` deletes/reinserts rows only in these sidecars and does not rewrite source tables.

- `messages_fts(message_id, subject, from_addr, snippet, sent_at, folder_kind)`
- `knowledge_messages_fts(knowledge_id, subject, from_addr, summary_text, category, sent_at)`
- `watch_signals_fts(signal_id, title, summary_text, author, url, published_at)`
- `watch_issue_stories_fts(issue_id, canonical_title, canonical_summary, primary_company_tag, last_seen_at)`

`wiki-search` returns JSON rows with `source_table`, `source_id`, `title`, `summary`, `timestamp`, and `rank`.

## Wiki semantic lint JSON
`wiki-semantic-lint` is read-only and reports generated/canonical boundary and evidence issues without editing wiki content or metadata queues.

```json
{
  "ok": false,
  "error_count": 1,
  "warning_count": 1,
  "issues": [
    {
      "severity": "error",
      "path": "queries/jinwang-jarvis-example.md",
      "code": "generated_metadata_missing",
      "message": "Generated report is missing required boundary metadata.",
      "evidence": "refresh_policy, operational_source_of_truth"
    }
  ]
}
```

## Key artifacts
- proposal runs: `data/proposals/proposal-run-*.json`
- digests: `data/digests/digest-*.md`
- weekly reviews: `data/digests/weekly-review-*.md`
- Discord briefings: `data/briefings/briefing-*.json`
- feedback audits: `data/feedback/feedback-<proposal_id>-*.json`
- backfill audits: `data/exports/backfill-*.json`
- watchlist syntheses: `data/watchlists/watchlist-*.json`
- wiki memory index: `queries/jinwang-jarvis-memory/index.md`
- auto-resume units: `systemd/*.service`, `systemd/*.timer`

## Hermes boundary
Hermes should interact with this project via:
- CLI entrypoints under `bin/`
- durable files under `data/` and `state/`
- watchlist / wiki synthesis produced by proposal runs or explicit `synthesize-knowledge` steps
- natural-language briefing artifacts that can be delivered to Discord for approval loops

The project should avoid direct reliance on Hermes core internals.
