#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_DIR="${1:-/home/jinwang/.hermes/hermes-agent}"
PATCH_DIR="$REPO_DIR/patches"

if [[ ! -d "$HERMES_DIR/.git" ]]; then
  echo "Hermes checkout not found: $HERMES_DIR" >&2
  exit 2
fi

patches=(
  "$PATCH_DIR/hermes-config-first-stt-tts-and-vad.patch"
)

for patch_path in "${patches[@]}"; do
  if [[ ! -f "$patch_path" ]]; then
    echo "Patch not found: $patch_path" >&2
    exit 2
  fi
  patch_name="$(basename "$patch_path")"
  if git -C "$HERMES_DIR" apply --reverse --check "$patch_path" >/dev/null 2>&1; then
    echo "Patch already applied: $patch_name"
    continue
  fi
  git -C "$HERMES_DIR" apply --3way --check "$patch_path"
  git -C "$HERMES_DIR" apply --3way "$patch_path"
  echo "Applied patch: $patch_name"
done

echo "Jarvis-managed Hermes patch application complete. Gateway was not restarted."
