#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
TARGET_PATH="$TARGET_DIR/hermes-local-stt.service"
PYTHON_BIN="${HERMES_LOCAL_STT_PYTHON:-$REPO_DIR/runtime/.venv/bin/python}"
SERVER_SCRIPT="$REPO_DIR/runtime/server.py"
HOST="${HERMES_LOCAL_STT_HOST:-127.0.0.1}"
PORT="${HERMES_LOCAL_STT_PORT:-8177}"

mkdir -p "$TARGET_DIR"
PYTHONPATH="$REPO_DIR" python3 - <<PY > "$TARGET_PATH"
from service.render import render_user_service
print(render_user_service(
    python_bin=${PYTHON_BIN@Q},
    server_script=${SERVER_SCRIPT@Q},
    host=${HOST@Q},
    port=int(${PORT@Q}),
    working_directory=${REPO_DIR@Q},
))
PY

systemctl --user daemon-reload
systemctl --user enable --now hermes-local-stt.service
systemctl --user status --no-pager hermes-local-stt.service || true

echo "Installed user service: $TARGET_PATH"
