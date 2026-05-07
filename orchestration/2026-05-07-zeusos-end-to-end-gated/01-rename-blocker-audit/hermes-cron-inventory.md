# Hermes cron inventory (controller-collected)

Collected with Hermes `cronjob(action="list")` during Phase 1.0 audit. No jobs were modified.

## Jobs with `workdir=/home/jinwang/workspace/jinwang-jarvis`

| Job ID | Name | Enabled | Deliver | Schedule | Notes |
|---|---|---:|---|---|---|
| `339afa4c2a54` | `jarvis-mail-daily-reminder-kst19` | true | `discord:1497918752212254760` | `0 10 * * *` | Jarvis workdir dependency |
| `cd4b4c6c521b` | `jarvis-mail-action-watch-15m` | true | `discord:1497918752212254760` | `10,25,40,55 * * * *` | Jarvis workdir dependency |
| `01cb26236d59` | `jarvis-hot-issues-merged-hourly` | true | `discord:1497916596981727354` | `0 * * * *` | Jarvis workdir dependency |
| `33fa5e22173e` | `jarvis-unified-daily-hot-issues-pdf-kst19` | true | `discord:1497915785576714351` | `0 10 * * *` | Jarvis workdir dependency |
| `dbb84957a3ac` | `personal-opportunity-radar-daily-kst19` | false | `discord:1496014213276241922` | `0 10 * * *` | Paused but still references Jarvis workdir |
| `f2b7a7a97901` | `news-center-hourly-kst` | false | `discord:1496014213276241922` | `5 * * * *` | Paused but still references Jarvis workdir |
| `2cd621dd2ce8` | `jarvis-hermes-skill-lifecycle-optimizer-weekly-kst0920` | true | `origin` | `20 0 * * 1` | Jarvis workdir dependency |

## Other relevant jobs

| Job ID | Name | Enabled | Workdir | Relevance |
|---|---|---:|---|---|
| `cc48d2fd3547` | `hermes-weekly-upgrade-deep-diff-kst1200` | false | `/home/jinwang/.hermes/hermes-agent` | Hermes Agent update/safety context |
| `12efcd4f1e34` | `wiki-daily-conversation-distill-kst2330` | true | `/home/jinwang/wiki` | Wiki generated/canonical policy context |
| `847a75be2ecd` | `weekly-local-software-module-update-deepreview-pdf-kst1230` | true | `/home/jinwang` | Hermes/local software review context |

## Gate implication

Any repo path rename, workdir move, package rename, or CLI rename would affect at least seven cron jobs. Therefore cron/workdir migration is a later `gateway_systemd`/automation approval gate, not Phase 1 code cleanup.
