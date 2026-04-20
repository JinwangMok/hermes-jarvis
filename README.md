# Hermes Jarvis

Hermes Jarvis helps you turn mail and calendar activity into a short action-oriented briefing.

It is for people who want to quickly see:
- what needs attention now
- what is still ongoing
- what became important recently
- which timed items are worth adding to a calendar

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
