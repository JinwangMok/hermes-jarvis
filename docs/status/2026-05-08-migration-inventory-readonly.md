# ZeusOS Migration Inventory — Read-only Pass

> Plain-language checkpoint: this is a warehouse inventory sheet, not a move. Nothing under `skills/`, `scripts/`, `data/`, or `state/` was moved or rewritten.

## Scope

Inventory roots:

- `skills/`
- `scripts/`
- `data/`
- `state/`

Purpose:

1. Identify which roots are code/config candidates and which are runtime truth.
2. Record migration risk before any file move.
3. Define safe next leaves for Agent OS-style rearchitecture.

Out of scope:

- No file moves.
- No runtime caller rewiring.
- No cron/systemd/Hermes gateway changes.
- No `credentials/**` reads.
- No raw wiki edits.

## Summary table

| Root | Exists | Tracked files | Untracked files | Total files | Approx bytes | Migration stance |
|---|---:|---:|---:|---:|---:|---|
| `skills/` | yes | 50 | 1 | 51 | 140,558 | migrate one skill at a time via compatibility bridge |
| `scripts/` | yes | 7 | 1 | 8 plus pycache | 47,925 excluding pycache in git view | classify into watchdog/tool/install before moving |
| `data/` | yes | 0 | 0 | 17,347 | 625,903,098 | runtime/data truth; no move before migration map + dry-run |
| `state/` | yes | 0 | 0 | 20 | 37,071,523 | runtime/state truth; no move before migration map + smoke |

## `skills/` inventory

Top-level entries:

| Entry | Shape | Files | Bytes | Candidate target | Notes |
|---|---|---:|---:|---|---|
| `discord-voice-stt-enhance` | external/custom skill bundle | 35 | 57,830 | `apps/skill-sets/custom-skills/discord-voice-stt-enhance/` or external skill lane | Contains runtime/service/scripts/tests; needs separate service boundary review. |
| `minerva` | custom workflow skill | 4 | 22,314 | `apps/skill-sets/custom-skills/minerva/` | Compatibility bridge already declared by `minerva`; runtime still legacy. |
| `minerva` | skill alias/legacy concept | 1 | 4,793 | bridge/alias metadata under `minerva` | Should not be moved before Minerva naming decision. |
| `styled-voice` | custom/external skill bundle | 11 | 55,621 | `apps/skill-sets/custom-skills/styled-voice/` or external skill lane | Has scripts/tests and external runtime expectations. |

Tracked files include skills for `discord-voice-stt-enhance`, `minerva`, `minerva`, and `styled-voice`.

Known untracked skill file:

```text
skills/minerva/references/zeusos-rearchitecture-leaf-pattern-2026-05-08.md
```

Migration stance:

- Do not bulk-move `skills/`.
- First safe operational leaf is not a move; it is one runtime caller reading `minerva` compatibility metadata while falling back to `skills/minerva`.
- Each future skill migration needs `app.yaml`, entrypoint, compatibility alias, tests, and rollback/no-op rollback note.

## `scripts/` inventory

Top-level entries:

| Entry | Shape | Tracked | Candidate target | Notes |
|---|---|---:|---|---|
| `arm-opencode-gateway-recovery.sh` | recovery/ops script | yes | keep external ops or `apps/tools/custom-defined-tools/opencode-manager/` later | Gateway safety-sensitive; do not move without Hermes restart safety review. |
| `gate_daily_hot_issues_delivery.py` | report quality gate | yes | `apps/watchdogs/news-center/` or report pipeline app | Coupled to reader-facing delivery gates. |
| `install.sh` | install script | yes | root tooling or `apps/tools` later | Needs packaging decision before move. |
| `lint_daily_hot_issues_content.py` | report lint | yes | `apps/watchdogs/news-center/` | Content-quality gate; likely news-center app component. |
| `patch_google_workspace_wrapper.py` | integration patch helper | yes | `apps/tools/custom-defined-tools/` | External integration helper; inspect before migration. |
| `render_daily_hot_issues_pdf.py` | report renderer | yes | `apps/watchdogs/news-center/` | Reader-facing output; requires quality-gate preservation. |
| `verify.sh` | repo verification script | yes | keep root tooling or `apps/tools` later | Operator verification script. |
| `mail-secretary-watchdog.py` | watchdog | no | `apps/watchdogs/email-handler/` candidate | Untracked dirty work; do not include in rearchitecture commits unless explicitly selected. |

Migration stance:

- Classify before moving: `watchdog`, `tool`, `installer`, `quality-gate`, `renderer`.
- Gateway recovery script is safety-critical and should not be moved in the same leaf as app migration.
- Mail secretary watchdog is unrelated dirty work until Jinwang explicitly selects it.

## `data/` inventory

Top-level entries:

```text
briefings
digests
exports
feedback
hermes-skill-lifecycle
minerva
intelligence
jarvis.sqlite
news-center
personal-radar
proposals
reports
secretary
snapshots
styled-voice-samples
user-feedback
watch
watchlists
```

Approximate size profile:

| Entry | Files | Bytes | Stance |
|---|---:|---:|---|
| `briefings` | 2,301 | 56,531,808 | generated/runtime data |
| `digests` | 2,385 | 10,188,369 | generated/runtime data |
| `exports` | 22 | 78,412 | generated/export data |
| `feedback` | 3 | 5,214 | user/runtime feedback |
| `hermes-skill-lifecycle` | 4 | 275,762 | lifecycle runtime data |
| `minerva` | 60 | 197,523 | Minerva runtime artifacts |
| `intelligence` | 2,103 | 2,856,556 | intelligence generated/runtime data |
| `jarvis.sqlite` | 1 | 0 | legacy placeholder/db |
| `news-center` | 356 | 32,484,754 | news-center runtime data |
| `personal-radar` | 26 | 94,686 | personal radar data |
| `proposals` | 2,384 | 232,084,019 | generated proposal artifacts |
| `reports` | 95 | 13,030,771 | generated reports |
| `secretary` | 67 | 82,487 | secretary runtime data |
| `snapshots` | 4,738 | 252,240,559 | runtime/source snapshots |
| `styled-voice-samples` | 2 | 607,933 | media/sample data |
| `user-feedback` | 1 | 1,791 | user feedback |
| `watch` | 433 | 3,601,098 | watch runtime data |
| `watchlists` | 2,366 | 21,541,356 | watchlist data |

Migration stance:

- Treat all `data/` as runtime/data truth.
- Do not move any `data/` subtree before:
  1. per-subtree source-of-truth decision,
  2. migration map,
  3. dry-run verifier,
  4. rollback command,
  5. post-move smoke test.
- Likely future mapping is not a move yet:
  - `data/minerva` -> future `apps/skill-sets/custom-skills/minerva` runtime data reference.
  - `data/news-center` and related reports -> `apps/watchdogs/news-center` runtime data reference.
  - `data/secretary` -> `apps/watchdogs/email-handler` runtime data reference.

## `state/` inventory

Top-level entries:

```text
.tmp_discord_briefing_message.txt
checkpoints.json
cron_tmp
discord_briefing_dispatch.log
external_hot_issue_state.json
hermes-skill-search.sqlite
hermes-skill-usage.json
minerva.db
important_mail_report_state.json
jarvis.sqlite3
jinwang_jarvis.sqlite3
last_discord_briefing_hash.txt
locks
mail_action_watch_state.json
mail_secretary_watchdog_delivered.json
merged_hot_issues_final.txt
merged_hot_issues_report_state.json
personal_intel.db
```

Approximate size profile:

| Entry | Files | Bytes | Stance |
|---|---:|---:|---|
| `personal_intel.db` | 1 | 31,227,904 | runtime DB; no move |
| `hermes-skill-search.sqlite` | 1 | 5,738,496 | runtime/index DB; no move |
| `mail_action_watch_state.json` | 1 | 36,858 | watchdog state; no move |
| `minerva.db` | 1 | 12,288 | Minerva runtime DB; no move |
| `cron_tmp` | 4 | 12,818 | cron temp state; no move |
| `locks` | 0 | 0 | locking root; no move |
| other JSON/log/hash files | 13 | small | runtime state; no move |

Migration stance:

- Treat all `state/` as runtime/state truth.
- Do not move or rewrite without live smoke and rollback.
- Future path resolver should keep `state` as compatibility root until all writers are audited.

## Proposed next leaves

### A. Runtime caller bridge for Minerva/Minerva

Goal: one ZeusOS-owned caller reads `minerva` compatibility metadata and falls back to `skills/minerva`.

Why next:

- It proves the declarative registry is operationally consumed.
- It avoids moving runtime truth.
- It advances aggressive acceptance without touching `data/` or `state/`.

Required guardrails:

- TDD first.
- No `data/` or `state/` mutation.
- No Hermes/gateway/systemd/cron edits.
- Explicit fallback to legacy path.
- Staged diff limited to caller, tests, and maybe small registry helper.

### B. CLI registry view after dirty isolation

Goal: expose `registry list/validate` for operator visibility.

Risk:

- `src/zeus_os/cli.py` is currently dirty from unrelated work, so this should wait unless the dirty work is isolated or intentionally selected.

### C. Script classification manifest

Goal: add declaration-only `app.yaml` contracts for news-center/email-handler/tool scripts without moving scripts.

Risk:

- Easy to overclaim migration if not explicitly marked declaration-only.

## Hard no-go list

- No `data/` or `state/` move.
- No `credentials/**` scan/read.
- No Hermes source, gateway, systemd, or cron mutation.
- No bulk `skills/` move.
- No `scripts/` move until each script is classified and tested.
