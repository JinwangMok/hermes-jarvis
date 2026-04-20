# Hermes Jarvis Setup Guide

Hermes Jarvis gives you a short briefing from your mail and calendar data.

Use it if you want to answer these questions quickly:
- What needs attention now?
- What is still ongoing?
- What became important recently?
- Which timed items should go on my calendar?

## Requirements
- Python 3.11+
- Hermes installed locally
- working mail access for collection
- Google Calendar access if you want calendar sync

## 1. Clone and install
```bash
git clone https://github.com/JinwangMok/hermes-jarvis.git
cd hermes-jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 2. Create local config
```bash
cp config/pipeline.yaml config/pipeline.local.yaml
cp config/sender-map.example.md config/sender-map.md
```

## 3. Edit the local config
Update these fields in `config/pipeline.local.yaml`:
- `accounts`
- `wiki_root`
- `classification.sender_map_path`
- `classification.self_addresses`
- `classification.work_accounts`
- `hermes.deliver_channel`

If you want sender-aware classification, set:
- `classification.sender_map_path: config/sender-map.md`

## 4. Fill the sender map
Example format:

```md
- Professor | Ada Lovelace | ada@example.org
- Ph.D. Student | Grace Hopper | grace@example.org / g.hopper@example.org
- M.S. Student | Demo User | you@example.com
```

## 5. Run the main steps
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
```

## 6. Approve or reject a proposal
Reject:
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

## 7. Run it automatically
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

## Practical notes
- Keep personal values in `config/pipeline.local.yaml`.
- Keep `config/sender-map.md` out of version control.
- The module path is still `jinwang_jarvis` for compatibility.
