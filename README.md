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
- natural-language briefing generation for Discord delivery / approval loops
- proposal feedback recorder (`allow` / `reject`) with optional calendar creation on allow
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

## Generate Discord briefing text
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.yaml
```

This writes a natural-language artifact under `data/briefings/` with:
- 최근 중요한 일
- 계속 중요한 일
- 새로 중요해진 일
- 추천 일정
- `캘린더에 등록할까요?` approval prompt text for the configured Discord channel

It also keeps a hierarchical wiki memory layer under `queries/jinwang-jarvis-memory/` so later conversations can look up recent / continuing / newly important work more efficiently.

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

If the user explicitly approves a timed proposal, you can immediately create the Google Calendar event:
```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other \
  --create-calendar
```

`record-feedback` now also regenerates the next briefing artifact automatically, so the approval loop immediately refreshes the remaining candidate list.

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
PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill-next --config config/pipeline.yaml --max-months 36
```

The backfill runner now performs **actual Himalaya pagination against source mailboxes** for the requested window and writes durable audit artifacts under `data/exports/`. `backfill-next` only extends history by the next 3-month slice (6m→9m→12m→...→36m), instead of doing a one-shot bulk jump.

## Bundle re-apply behavior
`./scripts/install.sh` now re-applies the Google Workspace wrapper compatibility patch before reinstalling systemd units, so the behavior survives the broader Hermes external-bundle update flow.
