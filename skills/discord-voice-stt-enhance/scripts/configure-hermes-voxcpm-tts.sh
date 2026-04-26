#!/usr/bin/env bash
set -euo pipefail

SERVER_BASE_URL="${VOXCPM_TTS_BASE_URL:-http://10.40.40.40/tts/v1}"
MODEL="${VOXCPM_TTS_MODEL:-voxcpm2}"
VOICE="${VOXCPM_TTS_VOICE:-A calm Korean male voice in his 30s, low-mid pitch, warm and composed, steady cadence, restrained emotion, same speaker identity across turns}"
STYLE_PROMPT="${VOXCPM_TTS_STYLE_PROMPT:-conversational Korean, even pacing, restrained emotion, stable delivery, minimal variation between turns}"
API_KEY="${VOXCPM_TTS_API_KEY:-local-voxcpm}"

cat <<YAML
tts:
  provider: openai
  openai:
    model: ${MODEL}
    voice: "${VOICE}"
    base_url: ${SERVER_BASE_URL}
    api_key: ${API_KEY}
    style_prompt: "${STYLE_PROMPT}"
    cfg_value: 2.5
    inference_timesteps: 12
YAML
