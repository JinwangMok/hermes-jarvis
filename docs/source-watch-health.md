# Watch source health telemetry

ZeusOS records per-source collection health for the external watch-source lane after every `collect-watch-signals` run. The telemetry is ZeusOS-owned state/artifact data and does not touch Hermes, cron, systemd, wiki raw files, or external services beyond the normal source fetches.

## Persistence

- SQLite table: `watch_source_health`
- Latest artifact: `data/watch/source-health/latest.json`
- Timestamped artifacts: `data/watch/source-health/source-health-<timestamp>.json`

Each record contains `last_attempt_at`, `fetch_status`, `exception_class`, `exception_message`, `items_seen`, `newest_published_at`, `items_after_recency`, and `stored_count`. Exception messages are whitespace-normalized, truncated, and redact simple token/key/password query fragments before persistence.

## Status meaning

- `ok`: source fetched and stored at least one globally recent item.
- `ok_html_fallback`: source stored items from a conservative HTML listing fallback after stale/error RSS.
- `ok_new_since_last_seen`: source stored an older but previously unseen high-value weekly/monthly item.
- `empty_feed`: fetch succeeded but no parseable items were found.
- `stale_feed`: items were seen, but the newest item is outside the global recency window.
- `already_seen_or_outside_source_window`: a high-value source returned older items that were already stored or outside its source-specific window.
- `recency_filtered`: items were seen but none survived freshness filtering.
- `error`: the source fetch/parser raised; collection continues for other sources.

## Source-specific policies

SemiAnalysis and VentureBeat AI use RSS first, then public homepage/category/archive listing metadata when RSS is stale. HPCwire remains staged/disabled by config, but if enabled later it uses at most one conservative HTML fallback after feed failure. Import AI, Latent Space, Interconnects, and Chips and Cheese can store previously unseen analysis items inside their source-specific window even when the global 24h recency gate would drop them.
