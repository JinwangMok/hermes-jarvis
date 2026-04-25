#!/usr/bin/env bash
set -euo pipefail

TARGET_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/hermes-local-stt.service"
systemctl --user disable --now hermes-local-stt.service || true
rm -f "$TARGET_PATH"
systemctl --user daemon-reload

echo "Removed user service: $TARGET_PATH"
