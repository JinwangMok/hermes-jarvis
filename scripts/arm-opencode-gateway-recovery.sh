#!/usr/bin/env bash
# Arm Jinwang's OpenCode/tmux gateway recovery belt from systemd or manual flows.
# Fast, non-blocking, fail-open: gateway startup must never be blocked by arming failure.
set -u

RECOVERY_ROOT="${HOME}/.hermes/recovery"
NODE_BIN="${HOME}/.local/share/fnm/node-versions/v24.14.1/installation/bin"
GUILD_ID="1487523027259490355"
CHANNEL_ID="1493529569926578276"
CONTEXT="Mok Lab. / #보라매봇-기본"
TRIGGER="${1:-systemd ExecStartPre for hermes-gateway.service}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || date +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RECOVERY_ROOT}/${STAMP}-systemd-gateway-start"
SESSION="oc-gw-recover-${STAMP:9:6}"
UNIT="opencode-gateway-recovery-${STAMP}"

mkdir -p "$RUN_DIR" "$RECOVERY_ROOT" 2>/dev/null || exit 0
printf '%s\n' "$TRIGGER" > "$RUN_DIR/trigger-command.txt" 2>/dev/null || true
printf '%s\nsession=%s\nunit=%s\nrun_dir=%s\ntrigger=%s\n' "$STAMP" "$SESSION" "$UNIT" "$RUN_DIR" "$TRIGGER" > "${RECOVERY_ROOT}/latest-systemd-arm.txt" 2>/dev/null || true

if [ -n "${HERMES_GATEWAY_RECOVERY_HOOK_DRY_RUN:-}" ]; then
  printf '{"would_arm":true,"launcher":"systemd-run","unit":"%s","session":"%s","run_dir":"%s"}\n' "$UNIT" "$SESSION" "$RUN_DIR"
  exit 0
fi

# Prevent recovery-worker storms on crash loops; one live recovery worker is enough.
if command -v systemctl >/dev/null 2>&1; then
  if systemctl --user list-units 'opencode-gateway-recovery-*.service' --state=active,activating --no-legend --plain 2>/dev/null | grep -q 'opencode-gateway-recovery-'; then
    printf '%s\n' "skipped: another opencode-gateway-recovery systemd unit already exists" > "$RUN_DIR/skipped.txt" 2>/dev/null || true
    exit 0
  fi
fi
if command -v tmux >/dev/null 2>&1; then
  if tmux list-sessions 2>/dev/null | awk -F: '{print $1}' | grep -q '^oc-gw-recover-'; then
    printf '%s\n' "skipped: another oc-gw-recover tmux session already exists" > "$RUN_DIR/skipped.txt" 2>/dev/null || true
    exit 0
  fi
fi

if ! command -v opencode >/dev/null 2>&1 && [ ! -x "${HOME}/.opencode/bin/opencode" ]; then
  printf '%s\n' "skipped: opencode not found" > "$RUN_DIR/skipped.txt" 2>/dev/null || true
  exit 0
fi

PROMPT_FILE="$RUN_DIR/prompt.txt"
LOG_FILE="$RUN_DIR/opencode.log"
cat > "$PROMPT_FILE" <<EOF
/ulw Hermes gateway restart recovery safety-belt for Jinwang.

You are an external OpenCode recovery worker. Do not modify source code. Sleep 180 seconds first. Then check Hermes gateway status and minimally repair only if inactive/failed.

Origin Discord context:
- Guild: ${GUILD_ID}
- Channel: ${CHANNEL_ID}
- Context: ${CONTEXT}
- Trigger: ${TRIGGER}
- Run dir: ${RUN_DIR}

After sleep, run these checks:
1. systemctl --user is-active hermes-gateway.service
2. systemctl --user show hermes-gateway.service -p MainPID -p ActiveState --no-pager
3. journalctl --user -u hermes-gateway.service -n 120 --no-pager

If inactive/failed, run minimal repair: systemctl --user restart hermes-gateway.service, then re-check active/PID/journal tail. If already active, do not restart.

Write a concise Korean report to ~/.hermes/recovery/latest-opencode-recovery.report with active state, PID, whether repair was needed, and key journal evidence. If possible, send the same concise report back to Discord channel ${CHANNEL_ID}; the report file is mandatory.
EOF

PATH_PREFIX="${NODE_BIN}:${HOME}/.opencode/bin:${PATH}"
q_path_prefix="$(printf '%q' "$PATH_PREFIX")"
q_home="$(printf '%q' "$HOME")"
q_prompt="$(printf '%q' "$PROMPT_FILE")"
q_log="$(printf '%q' "$LOG_FILE")"
worker_cmd="export PATH=${q_path_prefix}; cd ${q_home}; prompt=\$(cat ${q_prompt}); opencode run --model openai/gpt-5.5 --variant xhigh \"\$prompt\" > ${q_log} 2>&1"

if command -v systemd-run >/dev/null 2>&1; then
  systemd-run --user --unit="$UNIT" --description="OpenCode Hermes gateway recovery worker" \
    --property=CollectMode=inactive-or-failed --property=WorkingDirectory="$HOME" \
    /bin/bash -lc "$worker_cmd" >/dev/null 2>&1 && exit 0
  printf '%s\n' "systemd-run failed; falling back to tmux" > "$RUN_DIR/systemd-run-fallback.txt" 2>/dev/null || true
fi

if command -v tmux >/dev/null 2>&1; then
  tmux new-session -d -s "$SESSION" "bash" "-lc" "$worker_cmd" >/dev/null 2>&1 || true
fi
exit 0
