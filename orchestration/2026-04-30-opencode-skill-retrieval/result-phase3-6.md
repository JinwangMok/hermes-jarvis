# Hermes Skill Retrieval Sidecar Phase 3-6 Result

## Files changed

- `src/jinwang_jarvis/hermes_skill_search.py` — added Jarvis central telemetry ingestion for indexing/ranking, opt-in metadata-only search JSONL logging, widened candidate rescoring for exact name/path matches, and dependency-free gold query evaluation with Recall@K/MRR@K.
- `src/jinwang_jarvis/cli.py` — added `--telemetry-path` to `hermes-skill-search-index`, search logging flags to `hermes-skill-search`, and new `hermes-skill-search-eval` CLI.
- `tests/test_hermes_skill_search.py` — added tests for central telemetry merge, opt-in search logging, eval metrics, CLI eval/logging, and exact name/path ranking regression.
- `tests/fixtures/hermes_skill_gold_queries.json` — added the Phase 4 gold query fixture.
- `orchestration/2026-04-30-opencode-skill-retrieval/result-phase3-6.md` — this artifact.

Existing untracked Phase 1-2 files remain part of the sidecar work: `src/jinwang_jarvis/hermes_skill_context.py`, `tests/test_hermes_skill_context.py`, and `orchestration/2026-04-30-opencode-skill-retrieval/result.md`.

## Phase status

### Phase 3 — completed

- Search indexing now accepts a configurable `telemetry_path`, defaulting to `state/hermes-skill-usage.json`.
- Jarvis central telemetry is merged with legacy per-skill `.usage.json`; telemetry values override sidecar values while preserving `.usage.json` backward compatibility.
- Usage count, recency, and pinned values influence ranking deterministically, with small bounded boosts so telemetry cannot overwhelm lexical relevance.
- Search logging is opt-in via Python API and CLI `--search-log-path`; each JSONL event records timestamp, query, top_k, returned skill names, and optional selected/clicked skill only. It does not log full skill bodies.

### Phase 4 — completed

- Added `evaluate_skill_search()` plus `hermes-skill-search-eval` for Recall@K and MRR@K against a gold JSON fixture.
- Added `tests/fixtures/hermes_skill_gold_queries.json` with the requested query families.
- Improved ranking so exact skill name/path/token matches survive broad FTS candidate sets and are not buried before rescoring.
- Added regression coverage ensuring `hermes jinwang customization` ranks `hermes-jinwang-customization` first in an isolated corpus.

### Phase 5 — assessed; deferred heavy reranker

No embedding reranker was added. The lexical eval now passes the key exact-name/path and operational smoke cases, including `hermes jinwang customization` and `opencode tmux ulw`. The only weak real-corpus gold case was the broad semantic query `skill retrieval context budget`, where returned skills were adjacent but not the expected names. That is evidence for future synonym/query-expansion or an optional reranker interface, not enough to justify adding heavy embedding dependencies in this phase.

If Phase 5 is revisited, keep it source-untouched and optional: accept a precomputed/vector-score callback or lightweight reranker interface at search time, disabled by default, with no dependency required for the current CLI/tests.

### Phase 6 — design note

This sidecar can be exposed later as an MCP/custom tool or upstream PR candidate by wrapping the current Jarvis-owned API surface:

- `build_skill_search_index()` as a local sidecar refresh tool.
- `search_skills()` as a metadata-only retrieval tool with opt-in logging.
- `generate_skill_context()` as a budget-aware context assembly tool.
- `evaluate_skill_search()` as a regression/smoke gate for future ranking changes.

The source-untouched contract should stay explicit: all mutable state remains in Jarvis-owned `state/` paths or caller-provided temp DB/log files; Hermes skill directories, Hermes core, raw wiki, and gateway config are read-only inputs.

## Commands run and exact results

- `PYTHONPATH=src pytest tests/test_hermes_skill_search.py tests/test_hermes_skill_context.py tests/test_hermes_skill_lifecycle.py -q`
  - First final run after implementation: `19 passed in 1.65s`.
  - Re-run after widening search candidate pool: `19 passed in 1.65s`.
- `lsp_diagnostics` on:
  - `src/jinwang_jarvis/hermes_skill_search.py` — no diagnostics found.
  - `src/jinwang_jarvis/cli.py` — no diagnostics found.
  - `tests/test_hermes_skill_search.py` — no diagnostics found.
- `PYTHONPATH=src pytest -q`
  - First full run: `201 passed in 140.03s (0:02:20)`.
  - Re-run after widening search candidate pool: `201 passed in 126.97s (0:02:06)`.

## Real-corpus smoke results

All real-corpus smoke used a temp SQLite DB under `/tmp/jarvis-skill-smoke.*` and `--telemetry-path ""`; it did not write into `/home/jinwang/.hermes/skills`.

Index command:

```text
{"ok": true, "database_path": "/tmp/jarvis-skill-smoke.A8ga6I/skills.sqlite", "roots": [{"kind": "explicit", "path": "/home/jinwang/.hermes/skills"}], "telemetry_path": null, "counts": {"inserted": 159, "updated": 0, "skipped": 0, "deleted": 0, "errors": 0}, "errors": []}
```

Query `hermes jinwang customization` top 5:

```text
hermes-jinwang-customization
jinwang-jarvis
ktx-cancellation-watch
playbox
hermes-agent-skill-authoring
```

Query `opencode tmux ulw` top 5:

```text
opencode
jinwang-opencode-tmux-team
popular-web-designs
hermes-agent
claude-code
```

Gold eval against `tests/fixtures/hermes_skill_gold_queries.json` with `k=5`:

```text
query_count: 4
recall_at_k: 0.75
mrr_at_k: 0.75
```

Per-query outcomes:

- `source untouched jarvis` — Recall@5 `1.0`, MRR@5 `1.0`.
- `opencode tmux ulw` — Recall@5 `1.0`, MRR@5 `1.0`.
- `hermes jinwang customization` — Recall@5 `1.0`, MRR@5 `1.0`.
- `skill retrieval context budget` — Recall@5 `0.0`, MRR@5 `0.0`; see Phase 5 rationale.

## Protected/unrelated files

These files were already dirty before this run and were not edited:

- `scripts/lint_daily_hot_issues_content.py`
- `src/jinwang_jarvis/unified_daily_report.py`
- `tests/test_daily_hot_issues_content_quality.py`
- `tests/test_unified_daily_report.py`

No Hermes core files, `/home/jinwang/.hermes/skills` files, raw wiki files, or gateway config files were modified. Hermes gateway was not restarted or stopped.

## Risks and remaining work

- The real-corpus broad semantic query `skill retrieval context budget` remains weak under lexical-only retrieval. Prefer adding query expansion/synonym fixtures before considering embeddings.
- The search log is append-only JSONL and intentionally opt-in; downstream click/selection UX still needs to supply `selected_skill` or `clicked_skill` explicitly.
- The MCP/custom-tool exposure is documented but intentionally not implemented in this phase to avoid scope creep.
