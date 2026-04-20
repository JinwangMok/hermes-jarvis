# Hermes Jarvis Productization Guide

This guide explains how to turn Hermes Jarvis into a **wiki-backed personal mail assistant** that a fresh Hermes user can reproduce.

Target outcome:
- new mail is pulled into a local DB + wiki-backed memory layer
- thread / participant / project context keeps evolving over time
- a daily morning briefing is delivered to Discord at 08:00 KST
- daily/weekly informational mail is summarized together with action mail
- the same project can later expand to watch external sources and behave more like a true Jarvis assistant

## 1. Durable storage

Jarvis is local-first. The important state lives on disk:
- SQLite DB: `state/personal_intel.db`
- checkpoints: `state/checkpoints.json`
- wiki notes: `wiki/queries/...`
- intelligence artifacts: `data/intelligence/...`

That means reboot does **not** erase your memory layer as long as the filesystem persists.

## 2. Required pieces

- Python 3.11+
- local Hermes installation
- working mail access
  - recommended: Gmail + OAuth + Himalaya CLI
- optional Google Calendar access
- a wiki path (Obsidian-compatible recommended)
- optional Discord-connected Hermes instance for delivery

## 3. Gmail / Himalaya prerequisite

Jarvis assumes mail access already works. The recommended path is:
- create a Google OAuth client
- configure Himalaya with your Gmail account(s)
- verify folder listing and envelope listing
- verify access to `All Mail`

Quick checks:
```bash
himalaya account list
himalaya folder list -a personal
himalaya envelope list -a personal --folder INBOX --page 1 --page-size 5 --output json
```

For the knowledge lane, make sure `All Mail` / archive-like folders are accessible.

## 4. Local config

```bash
cp config/pipeline.yaml config/pipeline.local.yaml
cp config/sender-map.example.md config/sender-map.md
```

Update at least:
- `accounts`
- `wiki_root`
- `classification.sender_map_path`
- `classification.self_addresses`
- `classification.work_accounts`
- `hermes.deliver_channel`

Recommended:
- keep `wiki_root` inside your Obsidian vault
- point `hermes.deliver_channel` to the Discord channel/thread where briefings should be sent

## 5. First full run

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-knowledge-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-daily-intelligence --config config/pipeline.local.yaml
```

After this, you should have:
- operational lane from `INBOX + sent`
- knowledge lane from `All Mail`
- wiki intelligence notes
- a daily intelligence artifact

## 6. Operational lane vs knowledge lane

### Operational lane
Use for:
- what requires action now
- what needs reply / confirmation
- calendar candidates

Source:
- `INBOX`
- `sent`

### Knowledge lane
Use for:
- long-running context
- informational daily/weekly mail
- education / projects / patents / proposals / tech trends
- long-term memory notes

Source:
- `All Mail`

Keeping these lanes separate is what preserves both **operational precision** and **long-term recall**.

## 7. Reboot-safe automation

Recommended install:
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

Or:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli install-systemd --config config/pipeline.local.yaml --poll-minutes 5
```

### Important: enable linger
If you want user-level systemd timers to continue after reboot without requiring an interactive login, enable linger:

```bash
sudo loginctl enable-linger $USER
```

Verify with:
```bash
loginctl show-user $USER | grep Linger
systemctl --user status
systemctl --user list-timers
```

## 8. Daily morning briefing at 08:00 KST

The most practical architecture has two layers.

### Layer 1: frequent polling loop
Runs every 5 minutes and refreshes:
- mail collection
- calendar collection
- classification
- knowledge lane updates
- staged participant-cache backfill

### Layer 2: scheduled morning digest
Runs once per day at 08:00 KST and produces a human-facing briefing that includes:
- new mail from yesterday/today
- changes in ongoing important flows
- daily/weekly informational mail highlights
- proactive TODO / schedule suggestions
- Discord delivery

In short: **collect frequently, report at a fixed time**.

## 9. What the morning briefing should include

Recommended sections:
- what needs attention now
- what stayed important
- what became newly important
- advisor/boss/action-chain changes
- informational daily/weekly mail highlights
- suggested TODOs
- suggested calendar items

## 10. Why participant cache matters

To improve thread accuracy over time, Jarvis should accumulate header-level context:
- `Message-ID`
- `In-Reply-To`
- `References`
- `To / Cc / Reply-To / Delivered-To`

That enables:
- better thread grouping
- participant-role inference
- advisor action tracking
- project/work-item notes
- stronger daily briefings

## 11. Long-term expansion: watch sources

A true Jarvis-like assistant should eventually combine mail with additional watched sources:
- RSS / blogs
- CFP feeds
- startup / funding announcements
- vendor newsletters
- internal project dashboards

Recommended rule:
- DB/files are the source of truth
- the wiki is the synthesis + memory layer
- the daily digest merges mail + watched sources into one briefing

## 12. Public repo goal

The public repo is not just a code dump. It should let a new Hermes user:
1. connect Gmail/OAuth/Himalaya/wiki/Discord
2. reproduce a local-first assistant pipeline
3. operate a mail → memory → briefing → recommendation loop like a personal Jarvis

## 13. Checklist

### Minimum success
- [ ] `collect-mail` works
- [ ] `collect-calendar` works (optional)
- [ ] `classify-messages` works
- [ ] `collect-knowledge-mail` works
- [ ] `generate-daily-intelligence` works
- [ ] wiki notes appear

### Automation
- [ ] user systemd timer installed
- [ ] `loginctl enable-linger $USER`
- [ ] timers resume after reboot

### Morning briefing
- [ ] daily 08:00 KST schedule registered
- [ ] Discord delivery path verified
- [ ] new mail is reflected in the digest
- [ ] informational daily/weekly mail is included

## 14. Operating principles

- handle mail through polling, not IMAP push
- treat the wiki as memory/synthesis, not the source of truth
- separate operational lane and knowledge lane
- improve participant cache through staged backfill
- keep the morning briefing action-first, not noise-first
