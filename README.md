# Hermes Jarvis

Hermes Jarvis helps you turn mail and calendar activity into a short action-oriented briefing.

It is for people who want to quickly see:
- what needs attention now
- what is still ongoing
- what became important recently
- which timed items are worth adding to a calendar

## Example output
```text
Jarvis Briefing

- Needs attention now:
  - Reply to project review request
  - Confirm meeting agenda for Friday

- Still ongoing:
  - Budget draft with pending edits
  - Weekly lab coordination thread

- Newly important:
  - External seminar invite with a registration deadline

- Calendar suggestion:
  - Add "Project sync" on 2026-04-24 14:00
```

You can use this as a lightweight personal operations summary, or feed it into a Hermes workflow that asks whether a timed proposal should be added to your calendar.

## What you get
- mail collection from inbox + sent folders
- calendar collection from Google Calendar
- message classification
- proposal generation
- short briefing output
- allow / reject feedback for timed proposals
- optional calendar creation after approval
- weekly review output
- systemd timer setup for automatic polling

## 3-minute quick start
If you just want to see it working once:

```bash
git clone https://github.com/JinwangMok/hermes-jarvis.git
cd hermes-jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp config/pipeline.yaml config/pipeline.local.yaml
cp config/sender-map.example.md config/sender-map.md
```

Then edit `config/pipeline.local.yaml` and set:
- your accounts
- your `wiki_root`
- `classification.sender_map_path: config/sender-map.md`
- your own addresses in `classification.self_addresses`
- your work mailbox names in `classification.work_accounts`

Then run:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
```

That is enough to produce your first briefing artifact.

## Quick start
```bash
git clone https://github.com/JinwangMok/hermes-jarvis.git
cd hermes-jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp config/pipeline.yaml config/pipeline.local.yaml
cp config/sender-map.example.md config/sender-map.md
```

Then edit `config/pipeline.local.yaml`.

## Edit these settings first
In `config/pipeline.local.yaml`, update:
- `accounts`
- `wiki_root`
- `classification.sender_map_path`
- `classification.self_addresses`
- `classification.work_accounts`
- `hermes.deliver_channel`

Point `classification.sender_map_path` to `config/sender-map.md` if you want sender-aware classification.

## Run the pipeline
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
```

## Record a decision
Reject a proposal:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision reject \
  --reason-code low-value \
  --note "Not interested"
```

Approve and create a calendar event:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other \
  --create-calendar
```

## Run automatically
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

## Notes
- Keep personal values in `config/pipeline.local.yaml`.
- Keep `config/sender-map.md` private.
- The Python module path is still `jinwang_jarvis` for compatibility.

## Docs
- English guide: `docs/public-guide.en.md`
- 한국어 가이드: `docs/public-guide.ko.md`
- Public/private sync notes: `docs/public-sync.md`

## FAQ

### Do I need Hermes to use this?
No. The pipeline can run as a standalone local CLI workflow. Hermes becomes useful when you want delivery, conversational follow-up, or approval loops.

### Do I need Google Calendar?
No. You can still use mail collection, classification, proposals, and briefings without calendar creation. Calendar support is only needed if you want calendar collection or automatic event creation.

### Do I need a sender map?
No. The pipeline still works without one. A sender map simply improves prioritization and role-aware classification.

### Where should private values go?
Use `config/pipeline.local.yaml` and `config/sender-map.md`. Keep both out of version control.
