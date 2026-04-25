#!/usr/bin/env bash
set -euo pipefail

HOST="${HERMES_LOCAL_STT_HOST:-127.0.0.1}"
PORT="${HERMES_LOCAL_STT_PORT:-8177}"
URL="http://${HOST}:${PORT}/health"

curl -fsS "$URL"
