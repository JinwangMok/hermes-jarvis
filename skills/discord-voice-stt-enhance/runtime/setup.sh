#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${HERMES_LOCAL_STT_VENV:-$SCRIPT_DIR/.venv}"
UV_BIN="${UV_BIN:-uv}"
PYTHON_VERSION="${HERMES_LOCAL_STT_PYTHON_VERSION:-}"

if ! command -v "$UV_BIN" >/dev/null 2>&1; then
  echo "uv not found: $UV_BIN" >&2
  exit 1
fi

if [[ -n "$PYTHON_VERSION" ]]; then
  "$UV_BIN" venv --python "$PYTHON_VERSION" "$VENV_DIR"
else
  "$UV_BIN" venv "$VENV_DIR"
fi
"$UV_BIN" pip install --python "$VENV_DIR/bin/python" -r "$SCRIPT_DIR/requirements.txt"

echo "Runtime setup complete"
echo "uv env: $VENV_DIR"
echo "model(default): ${HERMES_LOCAL_STT_MODEL:-large-v3-turbo}"
echo "next: $SCRIPT_DIR/launch.sh"
