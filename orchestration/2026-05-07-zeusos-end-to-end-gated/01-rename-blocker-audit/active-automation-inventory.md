# Active automation inventory

## systemctl --user list-timers --all
NEXT                            LEFT LAST                              PASSED UNIT                                          ACTIVATES
Thu 2026-05-07 03:30:32 UTC 1min 10s Thu 2026-05-07 03:25:32 UTC 3min 49s ago jinwang-jarvis-hermes-health.timer            jinwang-jarvis-hermes-health.service
Thu 2026-05-07 06:00:00 UTC 2h 30min Thu 2026-05-07 03:00:23 UTC    28min ago snap.firmware-updater.firmware-notifier.timer snap.firmware-updater.firmware-notifier.service
Thu 2026-05-07 08:35:32 UTC  5h 6min Wed 2026-05-06 08:35:32 UTC      18h ago launchpadlib-cache-clean.timer                launchpadlib-cache-clean.service

3 timers listed.

## systemctl --user list-units --type=service --all
  UNIT                                                             LOAD      ACTIVE   SUB     DESCRIPTION
  hermes-gateway.service                                           loaded    active   running Hermes Agent Gateway - Messaging Platform Integration
  jinwang-jarvis-hermes-health.service                             loaded    inactive dead    Check Hermes gateway + Jarvis cron health and alert Discord
Legend: LOAD   → Reflects whether the unit definition was properly loaded.
        ACTIVE → The high-level unit activation state, i.e. generalization of SUB.
        SUB    → The low-level unit activation state, values depend on unit type.

## Hermes cron jobs
cronjob inventory not available from shell: No module named 'hermes_tools'
NOTE: Hermes cron inventory requires Hermes tool context; see controller summary if collected separately.

## Hermes plugin symlinks
/home/jinwang/.hermes/plugins/hermes_hooo_gateway
/home/jinwang/.hermes/plugins/hermes_jarvis_styled_voice_gateway
