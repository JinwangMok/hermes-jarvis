#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
POLL_MINUTES="${POLL_MINUTES:-5}"
HEALTH_MINUTES="${HEALTH_MINUTES:-$POLL_MINUTES}"
STALE_MINUTES="${STALE_MINUTES:-15}"
CONFIG_PATH="${JARVIS_CONFIG_PATH:-}"
ENABLE=1
INSTALL_GATEWAY=1

if [[ -z "$CONFIG_PATH" ]]; then
  if [[ -f "$ROOT_DIR/config/pipeline.local.yaml" ]]; then
    CONFIG_PATH="config/pipeline.local.yaml"
  else
    CONFIG_PATH="config/pipeline.yaml"
  fi
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --poll-minutes)
      POLL_MINUTES="$2"
      HEALTH_MINUTES="$2"
      shift 2
      ;;
    --health-minutes)
      HEALTH_MINUTES="$2"
      shift 2
      ;;
    --stale-minutes)
      STALE_MINUTES="$2"
      shift 2
      ;;
    --no-enable)
      ENABLE=0
      shift
      ;;
    --no-install-gateway)
      INSTALL_GATEWAY=0
      shift
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"
python3 "$ROOT_DIR/scripts/patch_google_workspace_wrapper.py"
CMD=(python3 -m jinwang_jarvis.cli install-standby-systemd --config "$CONFIG_PATH" --health-minutes "$HEALTH_MINUTES" --stale-minutes "$STALE_MINUTES")
if [[ "$ENABLE" != "1" ]]; then
  CMD+=(--no-enable)
fi
if [[ "$INSTALL_GATEWAY" == "1" ]]; then
  CMD+=(--install-gateway)
fi
PYTHONPATH=src "${CMD[@]}"

# The old Jarvis-owned polling timers are superseded by Hermes cron + the
# health watchdog. Keep them disabled so bundle reapply cannot resurrect a
# second scheduler path after Hermes updates.
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now jinwang-jarvis-cycle.timer jinwang-jarvis-weekly-review.timer >/dev/null 2>&1 || true
  systemctl --user disable --now jinwang-jarvis-cycle.service jinwang-jarvis-weekly-review.service >/dev/null 2>&1 || true
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi
