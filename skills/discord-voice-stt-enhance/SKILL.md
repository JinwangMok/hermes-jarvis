---
name: discord-voice-stt-enhance
description: External large-v3-turbo runtime, config wiring, and optional local service for Hermes Discord voice STT/TTS workflows.
---

# discord-voice-stt-enhance

Use this repo when you want to keep Discord voice-channel STT/TTS runtime infrastructure outside the main Hermes repository while still running a stronger local STT model on the same machine.

## Included runtime changes
- Local `faster-whisper` HTTP runtime for `large-v3-turbo`
- Thin `local_command` client for Hermes-to-local-runtime wiring
- Optional user `systemd` service installation helpers
- Config snippet generation for external-only wiring

## Register the external repo
Run:
```bash
scripts/install.sh --config ~/.hermes/config.yaml
```

## Set up the local STT runtime
Run:
```bash
runtime/setup.sh
runtime/launch.sh
```

## Configure Hermes
Run:
```bash
scripts/configure-hermes-local-stt.sh
```
Then copy the printed env and YAML snippet into `~/.hermes/.env` and `~/.hermes/config.yaml`.

## Optional persistent service
Run:
```bash
service/install-systemd.sh
```

## Verify
Run:
```bash
scripts/verify.sh /path/to/hermes-agent
```
