# Stage3D Plugin Config Cutover Result — Sanitized

## Action
- Switched live Hermes enabled plugin from `hermes-jarvis-styled-voice-gateway` to `hermes-zeus-styled-voice-gateway`.
- Restarted `hermes-gateway.service` with the OpenCode recovery safety belt armed.
- Removed raw `~/.hermes/config.yaml` before/after copies from repo artifacts before commit.

## Verification
- Gateway after restart: active.
- MainPID after restart: recorded in live journal during the run; rechecked later as active.
- Enabled plugin excerpt after cutover:
  - `hermes-minerva-gateway`
  - `hermes-zeus-styled-voice-gateway`
  - `jinwang-delivery-gate`
- Legacy styled-voice plugin entry: not enabled.

## Notes
- The gateway stop path timed out during drain and systemd killed the previous process, then started the new gateway successfully.
- No raw journal dump or live config snapshot is committed in this artifact.
