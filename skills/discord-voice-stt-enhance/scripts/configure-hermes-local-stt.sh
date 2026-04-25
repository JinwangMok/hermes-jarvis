#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$REPO_DIR/runtime"
SERVER_URL="${HERMES_LOCAL_STT_SERVER_URL:-http://127.0.0.1:8177}"
CLIENT_PY="${HERMES_LOCAL_STT_CLIENT_PY:-$RUNTIME_DIR/client.py}"

# Optional: add this to ~/.hermes/.env if you still want env-based fallback.
echo "HERMES_LOCAL_STT_SERVER_URL=${SERVER_URL}"
echo "HERMES_LOCAL_STT_COMMAND=python ${CLIENT_PY} --input {input_path} --output-dir {output_dir} --language {language} --model {model}"
echo
echo '# Config-first mode below avoids depending on HERMES_LOCAL_STT_* being present in the gateway service env.'
echo

cat <<YAML
stt:
  enabled: true
  provider: local_command
  local:
    model: large-v3-turbo
    language: ''
  local_command:
    command: python ${CLIENT_PY} --server-url ${SERVER_URL} --input {input_path} --output-dir {output_dir} --language {language} --model {model}
YAML
