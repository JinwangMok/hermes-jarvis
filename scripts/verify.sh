#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTEST_PYTHON=${HERMES_VERIFY_PYTHON:-}

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

cd "$ROOT_DIR"
python3 "$ROOT_DIR/scripts/patch_google_workspace_wrapper.py"
PYTHONPATH=src "$PYTEST_PYTHON" -m pytest -q tests/test_runtime.py tests/test_cli.py tests/test_briefing.py tests/test_proposals.py
