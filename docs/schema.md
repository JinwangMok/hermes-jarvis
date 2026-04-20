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
