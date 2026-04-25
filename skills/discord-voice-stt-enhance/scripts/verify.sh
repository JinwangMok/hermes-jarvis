#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_DIR="${1:-/home/jinwang/.hermes/hermes-agent}"
PYTEST_PYTHON="${HERMES_VERIFY_PYTHON:-}"

if [[ -z "$PYTEST_PYTHON" ]]; then
  if python3 -c 'import pytest' >/dev/null 2>&1; then
    PYTEST_PYTHON="python3"
  elif [[ -x "$HOME/.hermes/hermes-agent/venv/bin/python" ]]; then
    PYTEST_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
  else
    echo "Could not find a Python interpreter with pytest installed" >&2
    exit 1
  fi
fi

cd "$REPO_DIR"
"$PYTEST_PYTHON" -m pytest tests/test_runtime_helpers.py -q
"$PYTEST_PYTHON" -m pytest tests/test_service_render.py -q
"$PYTEST_PYTHON" -m py_compile runtime/helpers.py runtime/client.py runtime/server.py service/render.py

echo "Repo unit checks: ok"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
HERMES_LOCAL_STT_SERVER_URL="http://127.0.0.1:8177" "$REPO_DIR/scripts/configure-hermes-local-stt.sh" > "$TMPDIR/config-snippet.txt"

grep -q '^HERMES_LOCAL_STT_SERVER_URL=http://127.0.0.1:8177$' "$TMPDIR/config-snippet.txt"
grep -q '^HERMES_LOCAL_STT_COMMAND=python ' "$TMPDIR/config-snippet.txt"
grep -q '^  provider: local_command$' "$TMPDIR/config-snippet.txt"

echo "Config snippet checks: ok"

if [[ -d "$HERMES_DIR/.git" ]]; then
  git -C "$HERMES_DIR" status --short --branch
fi
