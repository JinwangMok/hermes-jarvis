# 2026-05-03 Jarvis watch-source upgrade evidence

Sanitized orchestration summary. Full transient OpenCode logs/prompts were intentionally not committed because they contain noisy QA probes and artificial secret-like test strings.

## Scope
- Watch-source health telemetry for external hot-issue/source registry lane.
- Conservative source-specific fallback/freshness policies for high-value analysis/media sources.
- Additional staged/verified source YAMLs for AI infra, semiconductors, Korean AI, and evaluation harness tracking.

## Safety boundaries
- No Hermes source changes.
- No `~/.hermes`, systemd, cron, raw wiki, secret, or gateway restart changes.
- HPCwire remains disabled/staged; fallback is conservative and only relevant if enabled later.
- HTML fallback is metadata/listing only; no paid-login scraping or anti-bot bypass.

## Verification
- Focused watch-source/Minerva regression suite passed during cleanup.
- Full suite passed: `240 passed`.
