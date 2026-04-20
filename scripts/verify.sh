#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"
python3 "$ROOT_DIR/scripts/patch_google_workspace_wrapper.py"
pytest -q tests/test_runtime.py tests/test_cli.py tests/test_briefing.py tests/test_proposals.py
