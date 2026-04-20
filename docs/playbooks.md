# Playbooks

## Bootstrap a fresh workspace
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli bootstrap --config config/pipeline.yaml
```

## Run tests
```bash
cd /home/jinwang/workspace/jinwang-jarvis
pytest -q
```

## Collect mail snapshots
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.yaml
```

## Collect calendar snapshots
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.yaml
```

## Classify messages
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.yaml
```

## Generate proposals and digest
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.yaml
```

This also updates the rolling watchlist artifact and the wiki note:
- `data/watchlists/watchlist-*.json`
- `/home/jinwang/wiki/queries/jinwang-jarvis-importance-shift-watchlist.md`

## Generate knowledge synthesis only
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli synthesize-knowledge --config config/pipeline.yaml
```

## Record proposal feedback
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other
```

## Generate weekly review
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli weekly-review --config config/pipeline.yaml
```

## Install systemd polling timers for reboot-safe resume
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli install-systemd --config config/pipeline.yaml --poll-minutes 5
```

## Run staged source backfill
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill --config config/pipeline.yaml --windows 1w
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill --config config/pipeline.yaml --windows 1m
```

This now performs real mailbox pagination against the source accounts and ingests window-matching messages into SQLite before reclassification.

## Hermes interaction model
Hermes should interact with jinwang-jarvis through:
- CLI commands
- durable files in `data/` and `state/`
- wiki notes generated from explicit summarization steps
