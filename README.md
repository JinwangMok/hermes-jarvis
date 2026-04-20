# Jinwang Jarvis

`jinwang-jarvis` is the deployable local workspace for Jinwang's personal mail/calendar intelligence pipeline.

## Goals
- learn from inbox + sent-mail behavior
- classify high-signal vs low-signal mail
- produce recommendation-first event/task proposals
- record explicit allow/reject feedback for proposals
- generate recurring digests and weekly reviews
- integrate with Hermes Agent at stable boundaries
- remain reproducible outside this chat transcript

## MVP status
Implemented end-to-end:
- workspace bootstrap + SQLite schema
- mail snapshot collector for inbox + sent folders
- calendar snapshot collector for Google Calendar events
- sender resolution and transparent message classifier
- proposal engine with calendar dedup + action signals
- markdown digest generation
- proposal feedback recorder (`allow` / `reject`)
- weekly review generator
- progressive source backfill runner
- systemd user service/timer installation for reboot-safe polling resume
- reproducible CLI/bin entrypoints and tests

## Expected layout
- `config/pipeline.yaml` — local runtime configuration
- `config/sender_rules.yaml` — optional sender overrides
- `config/subject_rules.yaml` — optional subject heuristics
- `config/workstream_rules.yaml` — optional workstream heuristics
- `state/personal_intel.db` — SQLite database
- `data/` — snapshots, exports, proposals, digests, feedback
- `src/jinwang_jarvis/` — Python package
- `bin/` — operational entrypoints

## Test
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

## Generate proposals + digest
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.yaml
```

## Record proposal feedback
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.yaml \
  --proposal-id <proposal_id> \
  --decision reject \
  --reason-code duplicate \
  --note "Already on calendar"
```

## Generate weekly review
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli weekly-review --config config/pipeline.yaml
```

## Install reboot-safe automatic polling
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli install-systemd --config config/pipeline.yaml --poll-minutes 5
```

This installs and enables user-level systemd timers so the pipeline resumes automatically after reboot/login and catches up missed runs with `Persistent=true`.

## Run progressive source backfill
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill --config config/pipeline.yaml --windows 1w
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill --config config/pipeline.yaml --windows 1m
```

The backfill runner now performs **actual Himalaya pagination against source mailboxes** for the requested window and writes durable audit artifacts under `data/exports/`.
