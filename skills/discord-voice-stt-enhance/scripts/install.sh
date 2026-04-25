#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HERMES_DIR="/home/jinwang/.hermes/hermes-agent"
CONFIG_PATH="${HOME}/.hermes/config.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hermes-dir)
      HERMES_DIR="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    *)
      HERMES_DIR="$1"
      shift
      ;;
  esac
done

python3 - "$REPO_DIR" "$CONFIG_PATH" <<'PY'
import sys
from pathlib import Path
import yaml

repo_root = Path(sys.argv[1]).expanduser().resolve()
config_path = Path(sys.argv[2]).expanduser()
config_path.parent.mkdir(parents=True, exist_ok=True)
if config_path.exists():
    data = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
else:
    data = {}
skills = data.setdefault('skills', {})
external_dirs = skills.setdefault('external_dirs', [])
repo_str = str(repo_root)
if repo_str not in external_dirs:
    external_dirs.append(repo_str)
config_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')
print(f'Updated {config_path} with skills.external_dirs += {repo_str}')
PY

echo "Registered external-only Discord voice bundle for $HERMES_DIR"
echo "No Hermes source patch was applied."
