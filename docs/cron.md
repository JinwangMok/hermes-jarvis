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
- latest natural-language briefing artifact under `data/briefings/`
- hierarchical memory notes under `/home/jinwang/wiki/queries/jinwang-jarvis-memory/`

## Briefing command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.yaml
```

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

If the user approves a timed proposal, add `--create-calendar` to materialize it immediately in Google Calendar.
The command also regenerates the latest briefing artifact so the next Discord report reflects the resolved state.

## Weekly review command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli weekly-review --config config/pipeline.yaml
```

## Install systemd timers
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli install-systemd --config config/pipeline.yaml --poll-minutes 5
sudo loginctl enable-linger $USER
```

This writes user units to `~/.config/systemd/user/` and mirrors them under `systemd/` inside the workspace.
If you want timers to continue after reboot **without an interactive login**, `loginctl enable-linger` is strongly recommended.

## Backfill command
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill --config config/pipeline.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill-next --config config/pipeline.yaml --max-months 36
```

## Polling principle
New mail is handled by **polling**, not IMAP push/async callbacks. The cycle timer periodically reruns collection/classification/proposal generation and resumes automatically after reboot via systemd user timers.

## Morning briefing pattern (recommended)
Use two layers:
1. 5-minute polling loop for data freshness
2. separate 08:00 KST digest for Discord delivery

Recommended digest steps:
- `collect-mail`
- `collect-calendar`
- `classify-messages`
- `collect-knowledge-mail` (or staged equivalent)
- `generate-daily-intelligence`
- deliver a human-facing morning summary to Discord

See `docs/productized-jarvis.en.md` / `docs/productized-jarvis.ko.md` for the end-to-end productized setup.
