# Hermes Jarvis

Hermes Jarvis helps you turn mail and calendar activity into a short action-oriented briefing.

## Who this is for
- people who want a compact summary of what needs attention now
- people who want mail-driven schedule suggestions with explicit approve/reject control
- people who prefer a local-first workflow with Hermes-friendly integration points

## Who this is not for
- people looking for a hosted SaaS product or one-click cloud setup
- people who do not want to manage local config for mail/calendar access
- teams that need a polished multi-user web UI out of the box

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
- All Mail-based knowledge lane and wiki intelligence notes
- participant/thread/project-aware memory notes
- daily morning briefing architecture for Discord delivery
- unified daily hot-issues report generation with News Center and Personal Opportunity Radar evidence merged into one advisory/derived surface

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
sudo loginctl enable-linger $USER
```

Use the 5-minute polling loop for collection/state refresh, then add a separate 08:00 KST morning digest schedule for Discord delivery.
See `docs/productized-jarvis.en.md` / `docs/productized-jarvis.ko.md` for the full productized workflow.

For today’s hot-issues PDF pipeline, use `generate-unified-daily-report` as the single daily report composer. Personal Opportunity Radar daily user-facing output is deprecated; its artifacts feed the `개인 기회/공고 검토` section inside 오늘의 핫이슈 and must not imply an item is actionable unless official URL, deadline/window, eligibility, and support contents are all present.

## Wiki search and semantic lint
Rebuild the local operational search sidecars after collecting mail/knowledge/watch data:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli wiki-search-index --config config/pipeline.local.yaml
```

`wiki-search-index` rewrites only the four SQLite FTS sidecar tables and is safe to rerun. Search those sidecars with JSON output:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli wiki-search --config config/pipeline.local.yaml --query "jongwon" --limit 10
```

Run the read-only wiki boundary/evidence checker with either config or an explicit wiki root:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli wiki-semantic-lint --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli wiki-semantic-lint --wiki-root /home/jinwang/wiki
```

`wiki-semantic-lint` reports generated/canonical/evidence issues as JSON only; it does not edit wiki files, queues, indexes, or logs.

## Notes
- Keep personal values in `config/pipeline.local.yaml`.
- Keep `config/sender-map.md` private.
- The Python module path is still `jinwang_jarvis` for compatibility.

## Docs
- English guide: `docs/public-guide.en.md`
- 한국어 가이드: `docs/public-guide.ko.md`
- Productized setup (EN): `docs/productized-jarvis.en.md`
- 제품화 가이드 (KO): `docs/productized-jarvis.ko.md`
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
