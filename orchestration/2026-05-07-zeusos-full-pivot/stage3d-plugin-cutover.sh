#!/usr/bin/env bash
set -euo pipefail
REPO=/home/jinwang/workspace/zeus-os
CONFIG=/home/jinwang/.hermes/config.yaml
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$REPO/orchestration/2026-05-07-zeusos-full-pivot/gateway-plugin-cutover-$STAMP"
mkdir -p "$RUN_DIR"

python3 - <<'PY'
from pathlib import Path
path = Path('/home/jinwang/.hermes/config.yaml')
text = path.read_text()
old = '  - hermes-jarvis-styled-voice-gateway\n'
new = '  - hermes-zeus-styled-voice-gateway\n'
if old not in text and new in text:
    print('already-cut-over')
elif old not in text:
    raise SystemExit('old styled voice plugin entry not found')
elif new in text:
    path.write_text(text.replace(old, ''))
else:
    path.write_text(text.replace(old, new))
PY

systemctl --user restart hermes-gateway.service
sleep 12
ACTIVE="$(systemctl --user is-active hermes-gateway.service || true)"
SHOW="$(systemctl --user show hermes-gateway.service -p MainPID -p ActiveState -p NRestarts --no-pager || true)"
{
  echo "# Stage3D plugin config cutover result"
  date -Is
  echo "run_dir=$RUN_DIR"
  echo "active=$ACTIVE"
  echo "$SHOW"
  echo '## configured plugins excerpt'
  python3 - <<'PY'
from pathlib import Path
text = Path('/home/jinwang/.hermes/config.yaml').read_text().splitlines()
inside = False
for line in text:
    if line.strip() == 'enabled:':
        inside = True
        print(line)
        continue
    if inside:
        if line.startswith('  - ') or line.startswith('    - ') or line.strip().startswith('- '):
            print(line)
        elif line and not line.startswith(' '):
            break
PY
  echo '## recent gateway journal omitted from committed artifact; inspect live journal if rollback is needed.'
} > "$RUN_DIR/result.md"
cat "$RUN_DIR/result.md"
if [ "$ACTIVE" != active ]; then
  python3 - <<'PY'
from pathlib import Path
path = Path('/home/jinwang/.hermes/config.yaml')
text = path.read_text()
path.write_text(text.replace('  - hermes-zeus-styled-voice-gateway\n', '  - hermes-jarvis-styled-voice-gateway\n'))
PY
  systemctl --user restart hermes-gateway.service || true
  exit 1
fi
