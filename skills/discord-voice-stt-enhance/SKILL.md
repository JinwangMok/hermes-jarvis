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

## Operational checkpoint before gateway restart
When asked to stop before restarting the gateway, the safe stopping point is:
1. commit and push the Jarvis/external-bundle changes;
2. run `scripts/verify.sh /home/jinwang/.hermes/hermes-agent` so the patch is tested against a temp clone;
3. apply `scripts/apply-hermes-patches.sh /home/jinwang/.hermes/hermes-agent` to the live checkout if disk changes are approved;
4. update `~/.hermes/config.yaml` only for the required voice keys, redacting/never printing secrets;
5. confirm `systemctl --user is-active hermes-gateway.service` and `MainPID` are unchanged.

Do not claim the running gateway uses the new code until it has been restarted. At this checkpoint the disk state is prepared, but the active process still has old code/config loaded.

## Patch/test pitfalls learned
- `git apply` reporting `corrupt patch at line <last>` often means the patch file is missing a trailing newline; ensure the patch ends in `\n`.
- Tests inside patch files should use fake non-secret tokens such as `local-test-token`; avoid real-looking API keys and do not print secret values.
- `git diff --check` may flag intentional whitespace lines inside `.patch` payloads. Do not auto-strip them blindly if doing so would change the patch semantics; verify with `git apply --check`/`--3way --check` instead.
- When adding the Discord PCM energy/VAD gate, existing voice reception tests that used all-zero PCM for “successful speech” became invalid. Treat this as a fixture bug, not a VAD regression: success-path synthetic PCM should use deterministic non-zero 16-bit samples (for example `+1000/-1000`), and silence rejection should be covered by a separate explicit test.
- After fixing live Hermes tests for a Jarvis-owned patch, propagate the additional live `git diff` back into `skills/discord-voice-stt-enhance/patches/hermes-config-first-stt-tts-and-vad.patch`, rerun `scripts/verify.sh /home/jinwang/.hermes/hermes-agent`, then commit the Jarvis patch bundle. Otherwise the live checkout can be green while the reusable external bundle stays stale.

## Verify
Run:
```bash
scripts/verify.sh /path/to/hermes-agent
```
