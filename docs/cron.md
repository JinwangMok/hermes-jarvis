# Cron plan for jinwang-jarvis

## Planned jobs
- `pi_collect_mail.py` — hourly
- `pi_collect_calendar.py` — hourly
- `pi_classify_messages.py` — every 2 hours
- `pi_run_cycle.py` — every 5 minutes via systemd user timer (recommended)
- `pi_weekly_review.py` — weekly via systemd user timer
- `pi_backfill.py` — manual / periodic staged source backfill via Himalaya pagination

## Bootstrap command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli bootstrap --config config/pipeline.yaml
```

## Mail collection command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.yaml
```

## Calendar collection command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.yaml
```

## Classification command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.yaml
```

## Proposal + digest command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.yaml
```

This also refreshes:
- watchlist artifact under `data/watchlists/`
- rolling wiki synthesis note at `/home/jinwang/wiki/queries/jinwang-jarvis-importance-shift-watchlist.md`

## Knowledge synthesis command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli synthesize-knowledge --config config/pipeline.yaml
```

## Feedback command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.yaml \
  --proposal-id <proposal_id> \
  --decision reject \
  --reason-code duplicate
```

## Weekly review command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli weekly-review --config config/pipeline.yaml
```

## Install systemd timers
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli install-systemd --config config/pipeline.yaml --poll-minutes 5
```

This writes user units to `~/.config/systemd/user/` and mirrors them under `systemd/` inside the workspace.

## Backfill command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill --config config/pipeline.yaml
```

## Polling principle
New mail is handled by **polling**, not IMAP push/async callbacks. The cycle timer periodically reruns collection/classification/proposal generation and resumes automatically after reboot via systemd user timers.
