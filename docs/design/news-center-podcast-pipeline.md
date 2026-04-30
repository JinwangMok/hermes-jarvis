# News Center + Podcast Pipeline

Status: implemented in Jarvis, no Hermes source/config changes required.

## Purpose

Daily hot-issues reports can be enriched with Naver News and Google News items grouped by:

- category: politics, economy, society, culture, technology, entertainment, world
- scope: domestic, international
- source: naver-news, google-news

The output is intentionally reader-facing. It avoids internal labels such as “신호” and keeps the same structure as the daily PDF report: 출처 성격, 확인된 사실, 왜 중요한가, 오늘 할 일, 근거, 불확실성. Source type must be explicit so official notices, news reports, community items, personal-post claims, and internal operations are not presented with the same trust level.

## Commands

Collect and write News Center artifacts plus wiki memory shards:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-news-center \
  --config config/pipeline.local.yaml \
  --per-source-limit 2
```

Generate the unified daily hot-issues report. This is now the single user-facing daily report surface: News Center and Personal Opportunity Radar artifacts are inputs, and opportunity items appear only inside `## 개인 기회/공고 검토` with the evidence gate applied.

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-unified-daily-report \
  --config config/pipeline.local.yaml \
  --date YYYY-MM-DD
```

The command writes `/home/jinwang/wiki/reports/hot-issues/daily/YYYY-MM-DD.md` and returns the render target `data/reports/daily-hot-issues-YYYY-MM-DD.pdf`. Personal Opportunity Radar should not be scheduled as a separate user-facing daily report; keep its source-audit/coverage artifacts as evidence inputs only. Live Hermes cron/controller changes are handled outside this repo after code verification.

Legacy append flow, kept for compatibility with older operators:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli append-news-center-to-daily-report \
  --daily-report /home/jinwang/wiki/reports/hot-issues/daily/YYYY-MM-DD.md \
  --news-markdown data/news-center/news-center-YYYYMMDDTHHMMSS+ZZZZ.md
```

Generate a TTS-ready podcast script:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-podcast-script \
  --daily-report /home/jinwang/wiki/reports/hot-issues/daily/YYYY-MM-DD.md \
  --output-path data/reports/daily-hot-issues-YYYY-MM-DD-podcast-script.md \
  --max-items 10
```

Render the enriched PDF:

```bash
python3 scripts/render_daily_hot_issues_pdf.py \
  /home/jinwang/wiki/reports/hot-issues/daily/YYYY-MM-DD.md \
  --pdf data/reports/daily-hot-issues-YYYY-MM-DD.pdf
```

## Wiki memory contract

Generated pages are derived reports, not canonical source of truth by existence alone.

- daily shard: `/home/jinwang/wiki/reports/news-center/daily/YYYY-MM-DD.md`
- category shards: `/home/jinwang/wiki/reports/news-center/categories/<category>.md`
- artifact JSON: `data/news-center/news-center-*.json`
- artifact markdown: `data/news-center/news-center-*.md`

The collector stores metadata, titles, short RSS/HTML excerpts, source URL, source name, publish date where available, category, scope, and uncertainty notes. It does not store full article bodies.

## Failure behavior

- Individual source failures are collected in the JSON `errors` list; remaining sources continue.
- Google News RSS queries are bounded to a recent window by default.
- Naver extraction keeps article links only and filters obvious navigation/media labels.
- Deduplication clusters by normalized Korean/English title tokens, so the same issue from Naver and Google is not repeated too aggressively.

## TTS handoff

Jarvis now produces a clean podcast script without raw URLs. The delivery layer can pass this script into its configured TTS provider. This repository does not modify Hermes cron or gateway settings.
