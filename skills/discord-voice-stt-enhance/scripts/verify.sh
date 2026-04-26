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
"$PYTEST_PYTHON" -m pytest tests/test_runtime_client.py -q
"$PYTEST_PYTHON" -m pytest tests/test_service_render.py -q
"$PYTEST_PYTHON" -m py_compile runtime/helpers.py runtime/client.py runtime/server.py service/render.py
bash -n scripts/install.sh scripts/apply-hermes-patches.sh scripts/configure-hermes-local-stt.sh scripts/configure-hermes-voxcpm-tts.sh

echo "Repo unit checks: ok"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
HERMES_LOCAL_STT_SERVER_URL="http://127.0.0.1:8177" "$REPO_DIR/scripts/configure-hermes-local-stt.sh" > "$TMPDIR/config-snippet.txt"

grep -q '^HERMES_LOCAL_STT_SERVER_URL=http://127.0.0.1:8177$' "$TMPDIR/config-snippet.txt"
grep -q '^HERMES_LOCAL_STT_COMMAND=python ' "$TMPDIR/config-snippet.txt"
grep -q '^  provider: local_command$' "$TMPDIR/config-snippet.txt"
grep -q '^    language: ko$' "$TMPDIR/config-snippet.txt"
grep -q '^    command: python .*--server-url http://127.0.0.1:8177' "$TMPDIR/config-snippet.txt"
"$REPO_DIR/scripts/configure-hermes-voxcpm-tts.sh" > "$TMPDIR/tts-snippet.txt"
grep -q '^  provider: openai$' "$TMPDIR/tts-snippet.txt"
grep -q '^    base_url: http://10.40.40.40/tts/v1$' "$TMPDIR/tts-snippet.txt"
grep -q '^    model: voxcpm2$' "$TMPDIR/tts-snippet.txt"

echo "Config snippet checks: ok"

if [[ -d "$HERMES_DIR/.git" ]]; then
  TMP_HERMES=$(mktemp -d)
  trap 'rm -rf "$TMPDIR" "$TMP_HERMES"' EXIT
  git clone --shared "$HERMES_DIR" "$TMP_HERMES/hermes-agent" >/dev/null
  "$REPO_DIR/scripts/apply-hermes-patches.sh" "$TMP_HERMES/hermes-agent"
  (cd "$TMP_HERMES/hermes-agent" && python -m py_compile tools/tts_tool.py tools/transcription_tools.py gateway/platforms/discord.py)
  (cd "$TMP_HERMES/hermes-agent" && python -m pytest \
    tests/tools/test_managed_media_gateways.py::test_openai_tts_accepts_configured_api_key_and_base_url \
    tests/tools/test_transcription_tools.py::TestTranscribeLocalCommand::test_configured_local_command_preferred_over_env \
    tests/gateway/test_voice_command.py::TestVoiceReceiver::test_check_silence_rejects_near_silence_buffer \
    tests/gateway/test_voice_command.py::TestVoiceReceiver::test_check_silence_returns_completed_utterance \
    -q)
  git -C "$HERMES_DIR" status --short --branch
fi
