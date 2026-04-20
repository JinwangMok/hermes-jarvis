# Public Setup Guide (English)

This guide explains how to use `jinwang-jarvis` as a reusable personal intelligence pipeline with Hermes.

## 1. Who this is for
Use this if you want Hermes to help summarize:
- what became important recently
- what stayed important over time
- what is newly important now
- which timed items are worth putting on your calendar

## 2. Minimum requirements
- Python 3.11+
- Hermes installed locally
- a working mail CLI flow (for this repo, Himalaya-based mail collection)
- Google Calendar access if you want calendar collection / creation

## 3. Local config strategy
Tracked file:
- `config/pipeline.yaml` → public-safe example

Private file (recommended):
- `config/pipeline.local.yaml` → your real paths, channels, accounts, addresses

The install script prefers `config/pipeline.local.yaml` automatically.

## 4. What you should customize
Edit these fields in `config/pipeline.local.yaml`:
- `accounts`
- `classification.sender_map_path`
- `classification.self_addresses`
- `classification.work_accounts`
- `hermes.deliver_channel`
- `wiki_root`

## 5. Sender map format
Use markdown bullets like:

```md
- Professor | Ada Lovelace | ada@example.org
- Ph.D. Student | Grace Hopper | grace@example.org / g.hopper@example.org
- M.S. Student | Demo User | you@example.com
```

## 6. Common workflow
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
```

## 7. Approval loop
When Hermes shows a timed proposal, record your decision:

Reject:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision reject \
  --reason-code low-value \
  --note "Not interested"
```

Allow + create calendar event:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other \
  --create-calendar
```

## 8. Automatic polling
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

## 9. Notes for Hermes users
- keep secrets and personal identifiers out of tracked config
- keep runtime state under `state/` and `data/`
- use wiki notes as synthesis memory, not raw source-of-truth
