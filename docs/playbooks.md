# Playbooks

## Bootstrap a fresh workspace
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli bootstrap --config config/pipeline.yaml
```

## Run tests
```bash
cd /home/jinwang/workspace/zeus-os
pytest -q
```

## Collect mail snapshots
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli collect-mail --config config/pipeline.yaml
```

## Collect calendar snapshots
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli collect-calendar --config config/pipeline.yaml
```

## Classify messages
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli classify-messages --config config/pipeline.yaml
```

## Generate proposals and digest
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli generate-proposals --config config/pipeline.yaml
```

This also updates the rolling watchlist artifact and the wiki note:
- `data/watchlists/watchlist-*.json`
- `/home/jinwang/wiki/queries/zeus-os-importance-shift-watchlist.md`

## Generate Discord briefing / approval prompt
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli generate-briefing --config config/pipeline.yaml
```

This writes a natural-language briefing artifact under `data/briefings/` for the configured Discord channel.
It also refreshes the hierarchical wiki memory notes under `queries/zeus-os-memory/`.

## Generate knowledge synthesis only
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli synthesize-knowledge --config config/pipeline.yaml
```

## Record proposal feedback
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli record-feedback \
  --config config/pipeline.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other
```

If the proposal already has a concrete start/end time and the user explicitly approves it, create the Calendar event immediately:
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli record-feedback \
  --config config/pipeline.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other \
  --create-calendar
```

This command also regenerates the next briefing so the approval loop immediately reflects the new state.

## Generate weekly review
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli weekly-review --config config/pipeline.yaml
```

## Install systemd polling timers for reboot-safe resume
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli install-systemd --config config/pipeline.yaml --poll-minutes 5
```

## Run staged source backfill
```bash
cd /home/jinwang/workspace/zeus-os
PYTHONPATH=src python3 -m zeus_os.cli backfill --config config/pipeline.yaml --windows 1w
PYTHONPATH=src python3 -m zeus_os.cli backfill --config config/pipeline.yaml --windows 1m
PYTHONPATH=src python3 -m zeus_os.cli backfill-next --config config/pipeline.yaml --max-months 36
```

This now performs real mailbox pagination against the source accounts and ingests window-matching messages into SQLite before reclassification. `backfill-next` extends history by only the next 3-month slice (6m→9m→12m→...→36m).

## Hermes interaction model
Hermes should interact with zeus-os through:
- CLI commands
- durable files in `data/` and `state/`
- wiki notes generated from explicit summarization steps
