#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
POLL_MINUTES="${POLL_MINUTES:-5}"
ENABLE=1

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
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"
CMD=(python3 -m jinwang_jarvis.cli install-systemd --config config/pipeline.yaml --poll-minutes "$POLL_MINUTES")
if [[ "$ENABLE" != "1" ]]; then
  CMD+=(--no-enable)
fi
PYTHONPATH=src "${CMD[@]}"
