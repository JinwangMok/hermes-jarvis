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
- Config-first STT command patch owned by Jarvis, not hand-edited in Hermes
- Discord PCM energy/VAD gate before STT to reduce hallucinations from silence/noise
- Config-first OpenAI-compatible TTS patch so `tts.openai.api_key/base_url` works without env vars
- VoxCPM fallback snippet for `http://10.40.40.40/tts/v1` / `voxcpm2`

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
STT snippet:
```bash
scripts/configure-hermes-local-stt.sh
```
TTS fallback snippet:
```bash
scripts/configure-hermes-voxcpm-tts.sh
```
Copy the printed YAML snippets into `~/.hermes/config.yaml`. The STT snippet also prints env-compatible fallbacks, but config-first mode is preferred.

## Apply Jarvis-owned Hermes runtime patches
Run:
```bash
scripts/apply-hermes-patches.sh /home/jinwang/.hermes/hermes-agent
```
This applies only the committed patch bundle from this Jarvis repo. It does **not** restart the gateway.

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
