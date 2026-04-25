# discord-voice-stt-enhance

External runtime/config repo for Hermes Discord voice-channel STT/TTS improvements, packaged outside the main `hermes-agent` repo.

## What this repo now contains
- Local `faster-whisper` HTTP runtime for `large-v3-turbo`
- Thin `local_command` client so Hermes can call the local runtime without new Hermes core changes
- Optional user-level `systemd` service installation for reboot-safe local STT startup
- Docs and helper scripts for wiring Hermes config and env

## Recommended architecture
- Keep upstream Hermes clean
- Keep Discord voice STT/TTS custom work in this external repo
- Run `large-v3-turbo` on the machine that actually has GPU access
- Point Hermes STT at `provider: local_command`
- Let Hermes call `runtime/client.py`, which POSTs to the configured runtime URL
- Prefer config-first command wiring so the gateway does not depend on `HERMES_LOCAL_STT_*` being present in the service environment
- If Hermes runs in a Linux VM without GPU passthrough, host the STT runtime on the Windows 11 machine and set the client `--server-url` to that host's reachable IP/port

## Repo layout
- `runtime/` — local STT HTTP server, thin client, uv-managed env setup, launch/health scripts
- `service/` — optional user `systemd` service helpers
- `scripts/` — external repo registration + Hermes wiring helpers
- `references/` — architecture and operations docs
- `examples/` — config snippets
- `tests/` — lightweight unit tests for helper logic in this repo

## Quick start

### 1) Register the external repo and print config wiring
```bash
~/workspace/discord-voice-stt-enhance/scripts/install.sh --config /home/jinwang/.hermes/config.yaml
```

### 2) Set up the STT runtime (uv-managed)

Linux host:
```bash
cd ~/workspace/discord-voice-stt-enhance
./runtime/setup.sh
```

Windows 11 GPU host:
```bat
cd %USERPROFILE%\workspace\discord-voice-stt-enhance
runtime\setup-windows.bat
```

### 3) Start the runtime manually

Linux host:
```bash
cd ~/workspace/discord-voice-stt-enhance
./runtime/launch.sh
```

Windows 11 GPU host:
```bat
cd %USERPROFILE%\workspace\discord-voice-stt-enhance
set HERMES_LOCAL_STT_HOST=0.0.0.0
runtime\launch-windows.bat
```
This now starts the server in the background and writes logs under `runtime\logs\`.
Use `runtime\stop-windows.bat` to stop it.

### 4) Check health
Linux host:
```bash
cd ~/workspace/discord-voice-stt-enhance
./runtime/healthcheck.sh
```

Windows 11 GPU host:
```bat
cd %USERPROFILE%\workspace\discord-voice-stt-enhance
runtime\healthcheck-windows.bat
```

### 5) Print Hermes wiring snippet
```bash
cd ~/workspace/discord-voice-stt-enhance
HERMES_LOCAL_STT_SERVER_URL=http://WINDOWS_HOST_IP:8177 ./scripts/configure-hermes-local-stt.sh
```
Copy the printed YAML into `~/.hermes/config.yaml`.
The printed `.env` lines are optional fallback only; config-first mode can work without them.

If Hermes and the STT runtime are on the same Linux machine, you can keep the default `http://127.0.0.1:8177`.
If Hermes is in a Linux VM and the STT runtime runs on Windows, replace `WINDOWS_HOST_IP` with the Windows host IP reachable from the VM.

### 6) Optional: install as user systemd service
```bash
cd ~/workspace/discord-voice-stt-enhance
./service/install-systemd.sh
```

### 7) Verify
```bash
cd ~/workspace/discord-voice-stt-enhance
./scripts/verify.sh /home/jinwang/.hermes/hermes-agent
```

## Key env defaults
See `runtime/local-stt.env.example`.
Important defaults:
- `HERMES_LOCAL_STT_MODEL=large-v3-turbo`
- `HERMES_LOCAL_STT_HOST=127.0.0.1` on single-host Linux, or `0.0.0.0` on the Windows GPU host so the VM can reach it
- `HERMES_LOCAL_STT_PORT=8177`
- `HERMES_LOCAL_STT_SERVER_URL=http://127.0.0.1:8177` for same-host use, or `http://WINDOWS_HOST_IP:8177` when Hermes runs in the VM and the runtime runs on Windows
- `HERMES_LOCAL_STT_COMPUTE_TYPE=int8_float16`

## Notes
- This repo keeps the feature outside the upstream Hermes repository.
- The current install/verify flow does **not** patch Hermes source files.
- The runtime is intended to load the model once and stay hot for low-latency Discord voice usage.
