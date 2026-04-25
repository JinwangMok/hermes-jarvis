#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${HERMES_LOCAL_STT_VENV:-$SCRIPT_DIR/.venv}"
HOST="${HERMES_LOCAL_STT_HOST:-127.0.0.1}"
PORT="${HERMES_LOCAL_STT_PORT:-8177}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Missing uv-managed runtime env: $VENV_DIR" >&2
  echo "Run $SCRIPT_DIR/setup.sh first." >&2
  exit 1
fi

exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/server.py" --host "$HOST" --port "$PORT"
