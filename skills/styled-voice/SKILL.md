---
name: styled-voice
description: Create speech in the user's style using Jarvis stored sample profiles or explicit audio references with the direct VoxCPM backend at 10.40.40.40:9100. Trigger via /styled-voice in Discord.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [voice-cloning, tts, voxcpm, discord, audio]
---

# /styled-voice

Use this skill when the user invokes `/styled-voice` and wants speech generated from a stored voice/style sample profile.

## Goal

Generate new audio in a selected voice/style by sending stored local audio samples to the **direct VoxCPM backend**:

- **Endpoint:** `http://10.40.40.40:9100/v1/audio/speech`
- **Do not use nginx `/tts/...` routes** for this skill.

## Runtime contract

This external skill does **not** patch Hermes runtime.

Only use audio file paths from the Jarvis styled-voice sample library, explicit operator-supplied paths, or URLs that Hermes already exposes in the message context. Do **not** assume hidden local cache paths are available, and do **not** guess undocumented Hermes internals.

If the request does not contain reusable attachment paths or URLs, use the stored sample profile instead. If that profile has no samples, ask the operator to add samples first.

## Jarvis sample library

Jarvis separates **sample upload/storage time** from **voice generation time**.

Default root:

```text
/home/jinwang/workspace/jinwang-jarvis/data/styled-voice-samples
```

Layout:

```text
<library>/<person>/<style>/*.wav|*.ogg|*.m4a|*.mp3|*.flac|*.opus|*.webm|*.aac
```

Profile shorthand:

- `default` → `default/default`
- `jongwon` → `jongwon/default`
- `jongwon/calm` → `jongwon/calm`

Manage samples through Jarvis:

```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src python3 -m jinwang_jarvis.cli styled-voice-samples init --profile default --profile jongwon
PYTHONPATH=src python3 -m jinwang_jarvis.cli styled-voice-samples add --profile jongwon --audio /abs/path/sample.wav
PYTHONPATH=src python3 -m jinwang_jarvis.cli styled-voice-samples list
PYTHONPATH=src python3 -m jinwang_jarvis.cli styled-voice-samples refs --profile jongwon
```

Generation with a stored profile:

```bash
python3 scripts/styled_voice_request.py \
  --voice jongwon \
  --input '생성할 문장' \
  --style-prompt 'calm, careful, conversational'
```

## Default behavior

Unless the user clearly specifies otherwise:

1. Use the stored `default` sample profile as `reference_audio`.
2. If the user names a profile such as `jongwon` or `jongwon/calm`, use that profile instead.
3. Use the text after `/styled-voice` as the target text to synthesize.
4. If the user also provides a style phrase (for example `차분하고 부드럽게, 살짝 웃는 느낌으로`), pass it as `style_prompt`.
5. Request `response_format=wav` from VoxCPM.
6. Save the result to a local temp/output `.wav` file.
7. Convert the final audio to OGG/Opus for Discord playback when replying.
8. Return it with `MEDIA:/absolute/path/to/output.ogg`.

## Concise user-facing guidance

If the user seems unsure, steer them toward this simple form:

```text
1) First save clean voice samples into a profile directory, e.g. default or jongwon
2) Write: /styled-voice [profile=jongwon] 생성할 문장
3) Optionally add a style phrase like “차분하고 부드럽게” or “soft, whispery, with small pauses”
```

Recommended sample quality:

- 3-15 seconds each
- single speaker
- minimal music/noise
- cleaner clips matter more than more clips

## Style phrasing cheat sheet

If the user asks how to request a stronger style, suggest phrases like these.

### hesitation / pauses
- `살짝 망설이듯`
- `조금 생각하면서 천천히`
- `with small pauses, slightly hesitant`

### slower pacing
- `조금 느리게`
- `또박또박, 급하지 않게`
- `slow, measured, unhurried`

### softness / warmth
- `부드럽고 다정하게`
- `차분하고 조심스럽게`
- `soft, warm, gentle`

### whisperiness / breathiness
- `작게 속삭이듯`
- `숨결이 조금 섞인 느낌으로`
- `soft whispery tone`

### brighter / smiling
- `살짝 웃는 느낌으로`
- `밝고 편안하게`
- `slightly smiling, conversational`

If the user provides no style guidance, do not overcomplicate it. Use a light neutral style prompt only when clearly helpful.

## Optional prompt-audio mode

If the user explicitly provides:

- one audio to use as **prompt audio**, and
- the **exact transcript** for that prompt audio,

then send:

- `prompt_audio=@...`
- `prompt_text=...`

and use the remaining clips as `reference_audio`.

If the user does **not** provide an exact transcript, do **not** guess one from STT for prompt mode unless they explicitly ask you to use the transcript as-is. Default back to reference-only mode.

## Required checks

Before calling the backend:

1. Resolve `--voice` / profile to stored sample audio under the Jarvis sample library, unless explicit `--reference-audio` paths are supplied.
2. Verify each referenced local file exists before using it.
3. If no reusable audio references are available, ask the operator to add samples with `styled-voice-samples add`.
4. If the synthesis text is empty, ask the user what sentence to generate.

## Preferred robust execution path

Use this retry strategy unless the user explicitly asks you to do something different:

1. Inspect the extracted files with `ffprobe`.
2. Decide whether direct upload looks safe.
3. If safe, try direct upload first.
4. If the backend fails, returns non-audio, or the media looks suspicious, normalize inputs to mono WAV with `ffmpeg`.
5. Retry automatically with normalized WAVs.
6. Convert the successful output to OGG/Opus.
7. Return the OGG file.

Discord-cached audio may arrive with misleading extensions/containers (for example `.ogg` files that actually contain AAC). Treat suspicious container/codec mismatches as a reason to normalize.

## Preferred helper command

If this repository is available locally, prefer the bundled helper script because it already implements the direct → normalize-retry → OGG flow and gives clearer error summaries.

Example with stored profile:

```bash
python3 scripts/styled_voice_request.py \
  --voice jongwon \
  --input '생성할 문장' \
  --style-prompt 'soft, careful, slightly smiling'
```

Example with explicit ad-hoc references:

```bash
python3 scripts/styled_voice_request.py \
  --input '생성할 문장' \
  --style-prompt 'soft, careful, slightly smiling' \
  --reference-audio /abs/path/sample1.ogg \
  --reference-audio /abs/path/sample2.m4a
```

It will:

- inspect inputs
- optionally skip unsafe direct upload
- retry automatically with normalized WAVs
- emit JSON with the chosen strategy and any backend failure summary
- produce both `.wav` and final `.ogg`

## Exact request pattern if you do it manually

Use the `terminal` tool with `curl -F ...` multipart form upload.

### Normalization flow

```bash
ffprobe /abs/path/sample1.ogg
ffmpeg -y -i /abs/path/sample1.ogg -ac 1 -ar 48000 /tmp/sample1.wav
ffmpeg -y -i /abs/path/sample2.ogg -ac 1 -ar 48000 /tmp/sample2.wav
```

### Reference-only example

```bash
curl -sS -X POST http://10.40.40.40:9100/v1/audio/speech \
  -o /tmp/styled-voice-output.wav \
  -F model=voxcpm2 \
  -F 'input=생성할 문장' \
  -F 'style_prompt=calm, slightly smiling, conversational' \
  -F response_format=wav \
  -F reference_audio=@/abs/path/sample1.wav \
  -F reference_audio=@/abs/path/sample2.m4a
```

### Prompt-audio + transcript example

```bash
curl -sS -X POST http://10.40.40.40:9100/v1/audio/speech \
  -o /tmp/styled-voice-output.wav \
  -F model=voxcpm2 \
  -F 'input=생성할 문장' \
  -F 'style_prompt=calm, slightly smiling, conversational' \
  -F response_format=wav \
  -F reference_audio=@/abs/path/ref1.wav \
  -F prompt_audio=@/abs/path/prompt.wav \
  -F 'prompt_text=프롬프트 오디오의 정확한 전사 텍스트'
```

## Output handling

After synthesis succeeds:

1. Verify the output file exists and is non-empty.
2. Convert to OGG/Opus for Discord playback:

```bash
ffmpeg -y -i /tmp/styled-voice-output.wav -c:a libopus -b:a 96k /tmp/styled-voice-output.ogg
```

3. Respond briefly and include:

```text
MEDIA:/absolute/path/to/output.ogg
```

## Failure handling

- If curl returns non-200 or the output is not a valid audio payload, summarize the backend error clearly.
- If the backend is unavailable, tell the user the direct VoxCPM backend at `10.40.40.40:9100` is not responding.
- If multiple audio files are attached and the user does not specify roles, use **reference-only mode** with all of them.
- If the user asks for “my voice style” and provides samples only, that is sufficient for reference-only mode.
- Do not mention nginx routes in the reply unless the user explicitly asks about operational issues.

## Response style

Be operational and concise:

- say what assumption you made about the uploaded files
- mention if you normalized/retried
- generate the audio
- return the file
