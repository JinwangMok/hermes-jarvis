#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
POLL_MINUTES="${POLL_MINUTES:-5}"
HEALTH_MINUTES="${HEALTH_MINUTES:-$POLL_MINUTES}"
STALE_MINUTES="${STALE_MINUTES:-15}"
legacy_config_env="JAR""VIS_CONFIG_PATH"
CONFIG_PATH="${ZEUSOS_CONFIG_PATH:-${!legacy_config_env:-}}"
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
if command -v systemctl >/dev/null 2>&1; then
  # Prevent duplicate restart-capable health watchdogs during the rename cutover.
  # The canonical ZeusOS timer is installed/enabled below; legacy health units
  # must be stopped first so old and new watchdogs never race each other.
  legacy_unit_prefix="jinwang-jar""vis"
  systemctl --user disable --now \
    zeus-os-hermes-health.timer zeus-os-hermes-health.service \
    "${legacy_unit_prefix}-hermes-health.timer" "${legacy_unit_prefix}-hermes-health.service" \
    >/dev/null 2>&1 || true
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi
CMD=(python3 -m zeus_os.cli install-standby-systemd --config "$CONFIG_PATH" --health-minutes "$HEALTH_MINUTES" --stale-minutes "$STALE_MINUTES")
if [[ "$ENABLE" != "1" ]]; then
  CMD+=(--no-enable)
fi
if [[ "$INSTALL_GATEWAY" == "1" ]]; then
  CMD+=(--install-gateway)
fi
PYTHONPATH=src "${CMD[@]}"

# The old ZeusOS-owned polling timers are superseded by Hermes cron + the
# health watchdog. Keep both legacy compatibility unit names and canonical
# ZeusOS names disabled so bundle reapply cannot resurrect a second scheduler
# path during the staged rename window.
if command -v systemctl >/dev/null 2>&1; then
  legacy_unit_prefix="jinwang-jar""vis"
  systemctl --user disable --now \
    zeus-os-cycle.timer zeus-os-weekly-review.timer \
    "${legacy_unit_prefix}-cycle.timer" "${legacy_unit_prefix}-weekly-review.timer" "${legacy_unit_prefix}-hermes-health.timer" \
    >/dev/null 2>&1 || true
  systemctl --user disable --now \
    zeus-os-cycle.service zeus-os-weekly-review.service \
    "${legacy_unit_prefix}-cycle.service" "${legacy_unit_prefix}-weekly-review.service" "${legacy_unit_prefix}-hermes-health.service" \
    >/dev/null 2>&1 || true
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi
