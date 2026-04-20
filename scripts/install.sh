#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
POLL_MINUTES="${POLL_MINUTES:-5}"
CONFIG_PATH="${JARVIS_CONFIG_PATH:-}"
ENABLE=1

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
      shift 2
      ;;
    --no-enable)
      ENABLE=0
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
CMD=(python3 -m jinwang_jarvis.cli install-systemd --config "$CONFIG_PATH" --poll-minutes "$POLL_MINUTES")
if [[ "$ENABLE" != "1" ]]; then
  CMD+=(--no-enable)
fi
PYTHONPATH=src "${CMD[@]}"
