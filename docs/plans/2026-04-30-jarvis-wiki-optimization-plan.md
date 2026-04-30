# Jarvis Wiki Optimization Final Consensus Plan

**Goal:** Add first-class wiki search, provenance/status helpers, and read-only semantic lint support to `jinwang-jarvis` while preserving the Markdown wiki as the human/canonical surface and `state/personal_intel.db` as the operational source of truth.

**Scope for the subsequent OpenCode implementation run:** one focused code/documentation/test change set. Implement only the tasks below. Do not perform broad wiki migrations, durable-page promotion, raw evidence rewrites, or dependency changes.

**Tech stack:** Python 3.11 stdlib only (`sqlite3`, `hashlib`, `json`, `re`, `dataclasses`, `pathlib`, `argparse` through the existing CLI), pytest, existing Jarvis config/bootstrap/CLI patterns.

---

## Non-negotiable constraints

1. Do not rewrite, delete, normalize, or body-lint anything under `/home/jinwang/wiki/raw/`.
2. Do not migrate existing generated pages from `queries/` to `reports/`; current generated pages under `queries/jinwang-jarvis-*` and `queries/external-hot-issues/` are tolerated by policy until a coordinated writer migration exists.
3. Do not overwrite or reformat unrelated dirty files:
   - `scripts/lint_daily_hot_issues_content.py`
   - `src/jinwang_jarvis/unified_daily_report.py`
   - `tests/test_daily_hot_issues_content_quality.py`
   - `tests/test_unified_daily_report.py`
4. Do not add runtime dependencies. In particular, do not add PyYAML, vector databases, embedding libraries, search daemons, or web services.
5. Generated report facts remain advisory unless explicitly promoted into durable pages with source links.
6. New commands must be deterministic and safe to run repeatedly.
7. Search indexing may modify only additive FTS sidecar tables inside the configured Jarvis SQLite database.
8. Semantic lint must report issues only; it must not edit wiki files, queues, indexes, or logs.

---

## Reviewer Consensus

- **Wiki governance reviewer:** The plan is acceptable only if generated/canonical boundaries stay explicit. Required decisions: keep `raw/` immutable, preserve generated pages as `authority: derived` or `advisory`, treat current `queries/jinwang-jarvis-*` generated pages as compatibility paths, and route future durable promotions through explicit source-linked review rather than automatic edits.
- **Jarvis runtime/SQLite reviewer:** The plan is safe if SQLite changes are additive and idempotent. Required decisions: use FTS5 virtual tables only as rebuildable sidecars, detect missing FTS5 without failing bootstrap, avoid triggers in this first implementation, never rewrite source tables, and make `wiki-search-index` delete/reinsert only FTS rows.
- **UX/search/report reviewer:** The plan is useful for Hermes if all command outputs are machine-readable JSON with stable fields. Required decisions: expose simple CLI commands, normalize search rows across source tables, include source IDs and timestamps for follow-up, and make lint issues specific enough to route future review or report-quality fixes.
- **Final agreed decisions:** Implement explicit rebuild search, reusable evidence/status rendering helpers, read-only semantic lint, and one low-risk integration in the generated watchlist writer. Defer migrations, triggers, automatic promotion, external search, and review-queue mutation.

---

## Acceptance criteria for the next run

The implementation is done when all of the following are true:

1. `bootstrap_workspace()` still creates existing directories/tables and also attempts idempotent FTS5 sidecar setup without crashing when FTS5 is unavailable.
2. `wiki-search-index` and `wiki-search` emit JSON only and work repeatedly against a temporary test database.
3. `wiki_contract.py` can render deterministic evidence lines and generated-report status blocks with obvious secrets redacted.
4. `wiki-semantic-lint` reports generated/canonical boundary issues and evidence gaps without mutating wiki content.
5. `synthesize-knowledge` adds a status block to `queries/jinwang-jarvis-importance-shift-watchlist.md` without changing watchlist scoring behavior.
6. README and schema documentation describe only the new commands, FTS sidecar tables, and semantic lint JSON shape.
7. The unrelated dirty files listed above are untouched.

---

## Exact files for the next implementation run

### Modify

- `src/jinwang_jarvis/bootstrap.py`
- `src/jinwang_jarvis/cli.py`
- `src/jinwang_jarvis/wiki_contract.py`
- `src/jinwang_jarvis/knowledge.py`
- `tests/test_bootstrap.py`
- `tests/test_cli.py`
- `tests/test_knowledge.py`
- `README.md`
- `docs/schema.md`

### Create

- `src/jinwang_jarvis/wiki_search.py`
- `src/jinwang_jarvis/wiki_semantic_lint.py`
- `tests/test_wiki_search.py`
- `tests/test_wiki_contract.py`
- `tests/test_wiki_semantic_lint.py`

### Do not edit in the next run

- `scripts/lint_daily_hot_issues_content.py`
- `src/jinwang_jarvis/unified_daily_report.py`
- `tests/test_daily_hot_issues_content_quality.py`
- `tests/test_unified_daily_report.py`
- Any file under `/home/jinwang/wiki/raw/`
- Any canonical wiki page under `/home/jinwang/wiki/entities/`, `/home/jinwang/wiki/concepts/`, `/home/jinwang/wiki/comparisons/`, or `/home/jinwang/wiki/queries/`

---

## Task sequence for the next implementation run

### Task 0 — Preflight guardrails

1. Run `git status --short` and note the unrelated dirty files before editing.
2. Inspect `src/jinwang_jarvis/bootstrap.py`, `src/jinwang_jarvis/cli.py`, `src/jinwang_jarvis/wiki_contract.py`, `src/jinwang_jarvis/knowledge.py`, `tests/test_bootstrap.py`, `tests/test_cli.py`, and `tests/test_knowledge.py` immediately before editing.
3. Confirm no planned edit overlaps the unrelated dirty files.

### Task 1 — Add additive FTS5 bootstrap support

**Files:** `src/jinwang_jarvis/bootstrap.py`, `tests/test_bootstrap.py`, `tests/test_wiki_search.py`

Implementation requirements:

1. Add `ensure_search_indexes(conn: sqlite3.Connection) -> dict[str, object]`.
2. Detect FTS5 by attempting a temporary FTS5 table inside the same connection and catching `sqlite3.OperationalError`; if unavailable, return `{"fts5_available": False, "reason": "fts5_unavailable"}` and do not raise.
3. Create these virtual tables with `CREATE VIRTUAL TABLE IF NOT EXISTS ... USING fts5(...)` only when FTS5 is available:
   - `messages_fts(message_id UNINDEXED, subject, from_addr, snippet, sent_at UNINDEXED, folder_kind UNINDEXED)`
   - `knowledge_messages_fts(knowledge_id UNINDEXED, subject, from_addr, summary_text, category UNINDEXED, sent_at UNINDEXED)`
   - `watch_signals_fts(signal_id UNINDEXED, title, summary_text, author, url UNINDEXED, published_at UNINDEXED)`
   - `watch_issue_stories_fts(issue_id UNINDEXED, canonical_title, canonical_summary, primary_company_tag UNINDEXED, last_seen_at UNINDEXED)`
4. Call `ensure_search_indexes(conn)` from `bootstrap_workspace(config)` after existing base tables and additive column migrations.
5. Do not add triggers, migrations that rewrite source tables, or destructive statements against non-FTS tables.

Tests:

- In `tests/test_bootstrap.py`, assert FTS tables exist when FTS5 is available and skip/assert the fallback payload when the local SQLite build lacks FTS5.
- In `tests/test_wiki_search.py`, assert repeated `ensure_search_indexes(conn)` calls are idempotent.

### Task 2 — Add operational search module and CLI commands

**Files:** `src/jinwang_jarvis/wiki_search.py`, `src/jinwang_jarvis/cli.py`, `tests/test_wiki_search.py`, `tests/test_cli.py`

Implementation requirements:

1. Implement `rebuild_operational_search_index(database_path: Path) -> dict[str, object]`.
2. Implement `search_operational_index(database_path: Path, query: str, limit: int = 10) -> dict[str, object]`.
3. Rebuild behavior:
   - Open the configured SQLite database.
   - Call `ensure_search_indexes(conn)`.
   - If FTS5 is unavailable, return `{"ok": False, "reason": "fts5_unavailable", ...}`.
   - Delete and reinsert rows only in the four FTS sidecar tables.
   - Populate FTS rows from `messages`, `knowledge_messages`, `watch_signals`, and `watch_issue_stories` using `COALESCE` for nullable text fields.
4. Search behavior:
   - Query all available FTS sidecar tables.
   - Use parameterized SQL for the FTS query and limit values.
   - Return JSON-serializable rows with stable fields: `source_table`, `source_id`, `title`, `summary`, `timestamp`, `rank`.
   - If the query syntax is invalid for FTS, return `{"ok": False, "reason": "invalid_query", ...}` instead of crashing.
5. CLI commands:
   - `wiki-search-index --config config/pipeline.local.yaml`
   - `wiki-search --config config/pipeline.local.yaml --query "jongwon" --limit 10`
6. CLI output must be JSON only and must follow the existing `main([...])` testing pattern.

Tests:

- Insert sample rows into all four source tables, rebuild, and query English/Korean terms.
- Assert expected source IDs appear in normalized result rows.
- Assert rebuild is repeatable and does not duplicate results.
- Add CLI smoke tests via `main([...])` and `capsys` that parse stdout as JSON.

### Task 3 — Add evidence and generated-report status helpers

**Files:** `src/jinwang_jarvis/wiki_contract.py`, `tests/test_wiki_contract.py`

Implementation requirements:

1. Add frozen dataclass `EvidenceRef` with fields:
   - `source_id: str`
   - `source_kind: str`
   - `source_url: str = ""`
   - `source_hash: str = ""`
   - `observed_at: str = ""`
   - `confidence: float | None = None`
2. Add `stable_source_hash(payload: object) -> str` using canonical JSON (`sort_keys=True`, compact separators, `ensure_ascii=False`) plus SHA256.
3. Add redaction for obvious secret assignments before rendering Markdown: `password=...`, `token=...`, `api_key=...`, `secret=...`, and uppercase variants should render their values as `[REDACTED]`.
4. Add `render_evidence_line(label: str, evidence: EvidenceRef) -> str`.
5. Add `render_status_block(...) -> list[str]` that renders stable headings:
   - `## Status`
   - `- TL;DR: ...`
   - `- Current status: ...`
   - `- Last verified: ...`
   - `- Evidence coverage: ...`
   - `- Open questions: ...`
6. Keep helpers generic and deterministic; do not read or write files inside these helper functions.

Tests:

- Hashes are deterministic regardless of dict key order.
- Evidence markdown includes source ID, kind, hash/date/confidence when present.
- Redaction works for token/password/api key/secret-style values.
- Status block headings and field order are stable.

### Task 4 — Add read-only semantic wiki lint

**Files:** `src/jinwang_jarvis/wiki_semantic_lint.py`, `src/jinwang_jarvis/cli.py`, `tests/test_wiki_semantic_lint.py`, `tests/test_cli.py`

Implementation requirements:

1. Implement `lint_wiki_semantics(wiki_root: Path) -> dict[str, object]`.
2. Scan Markdown files under the wiki root while excluding `.git`, `_archive`, and body checks under `raw/`.
3. Parse simple YAML frontmatter with local stdlib logic only. Support scalar strings, booleans, and one-line bracket lists well enough for current Jarvis-generated frontmatter.
4. Report issues with stable fields: `severity`, `path`, `code`, `message`, `evidence`.
5. Return summary fields: `ok`, `error_count`, `warning_count`, `issues`.
6. Checks to implement:
   - Generated report paths under `reports/`, `queries/jinwang-jarvis-*`, and `queries/external-hot-issues/` are missing one of `generated: true`, `authority`, `refresh_policy`, or `operational_source_of_truth`.
   - Generated pages use canonicalizing phrases such as `source of truth`, `canonical`, or `확정 사실` without nearby evidence/status disclaimers.
   - Opportunity/actionable language such as `신청 가능`, `apply now`, or `actionable` lacks a direct non-homepage URL and date/deadline evidence.
   - Durable pages under `entities/`, `concepts/`, `comparisons/`, and durable `queries/` have `sources: []` and strong claim markers such as `must`, `always`, `확정`, `현재`, or `source of truth`; report this as a warning, not an error.
   - Reader-facing generated daily reports are missing a status block; report this as a warning.
7. CLI commands:
   - `wiki-semantic-lint --config config/pipeline.local.yaml`
   - `wiki-semantic-lint --wiki-root /home/jinwang/wiki`
8. The command must not modify `_meta/review-queue/`, `_meta/ingestion-queue.md`, `index.md`, `log.md`, generated reports, or durable pages.

Tests:

- Build temporary wiki fixtures for generated reports, durable pages, and raw files.
- Assert errors/warnings are classified correctly.
- Assert raw file bodies are not linted.
- Add a CLI smoke test and parse stdout as JSON.

### Task 5 — Apply the status block to one generated surface

**Files:** `src/jinwang_jarvis/knowledge.py`, `tests/test_knowledge.py`

Implementation requirements:

1. Import and use `render_status_block` in `_write_wiki_summary(...)` only.
2. Insert the status block immediately after `# Jinwang Jarvis Importance Shift Watchlist` and before `## Why this page exists`.
3. Use deterministic values:
   - TL;DR: include the current watchlist candidate count.
   - Current status: `derived watchlist; not canonical`.
   - Last verified: the generated date from `generated_at[:10]`.
   - Evidence coverage: mention the latest proposal artifact and `wiki_operational_source(config)`.
   - Open questions: mention that human review is required before durable promotion.
4. Do not change watchlist scoring, source filtering, DB writes, index updating, or log behavior.

Tests:

- Extend `test_synthesize_knowledge_creates_watchlist_artifact_and_wiki_summary` to assert the status block exists.
- Keep existing assertions for `generated: true`, `generator: jinwang-jarvis`, `authority: derived`, and `operational_source_of_truth`.

### Task 6 — Document commands and schema additions

**Files:** `README.md`, `docs/schema.md`

Implementation requirements:

1. Add a concise README section for:
   - `wiki-search-index`
   - `wiki-search`
   - `wiki-semantic-lint`
2. Document that `wiki-search-index` rewrites only FTS sidecar tables and is safe to rerun.
3. Document that `wiki-semantic-lint` is read-only and reports generated/canonical/evidence issues.
4. Add `docs/schema.md` entries for the four FTS sidecar tables and the semantic lint JSON output shape.
5. Do not document broad migrations, embeddings, automatic durable promotion, or features not implemented in the same run.

---

## Required verification for the next implementation run

Run these after implementation:

```bash
PYTHONPATH=src pytest tests/test_wiki_search.py tests/test_wiki_contract.py tests/test_wiki_semantic_lint.py tests/test_knowledge.py tests/test_cli.py tests/test_bootstrap.py -q
PYTHONPATH=src python -m compileall src
```

Manual QA must also execute the actual feature paths in a temporary or safe local workspace:

```bash
PYTHONPATH=src python -m jinwang_jarvis.cli bootstrap --config <temp-pipeline.yaml>
PYTHONPATH=src python -m jinwang_jarvis.cli wiki-search-index --config <temp-pipeline.yaml>
PYTHONPATH=src python -m jinwang_jarvis.cli wiki-search --config <temp-pipeline.yaml> --query "jongwon" --limit 5
PYTHONPATH=src python -m jinwang_jarvis.cli wiki-semantic-lint --wiki-root <temp-wiki-root>
```

Expected evidence:

- Test command exits with code 0.
- Compile command exits with code 0.
- Search/index/lint commands print parseable JSON and no non-JSON chatter.
- `git diff --name-only` contains only the intended implementation files and does not include the unrelated dirty files listed in this plan.

---

## Rollback notes

- FTS changes are additive sidecars. To roll back DB state manually, drop only these sidecar tables:
  - `DROP TABLE IF EXISTS messages_fts;`
  - `DROP TABLE IF EXISTS knowledge_messages_fts;`
  - `DROP TABLE IF EXISTS watch_signals_fts;`
  - `DROP TABLE IF EXISTS watch_issue_stories_fts;`
- Reverting code changes in `bootstrap.py`, `wiki_search.py`, `wiki_semantic_lint.py`, `wiki_contract.py`, `knowledge.py`, `cli.py`, README, schema docs, and the new tests restores previous behavior.
- `wiki-search-index` should not affect source tables; if it does, treat that as a bug and revert before retrying.
- The watchlist status block appears only when the generated watchlist writer runs. It can be removed by reverting `knowledge.py` and regenerating the page from the previous code, with no durable wiki migration required.
- Semantic lint is read-only; rollback is deleting/reverting the module and CLI command.

---

## Explicitly rejected ideas

1. **Vector embeddings or external search engines:** rejected because the current requirement is local, stdlib-only, and operationally simple.
2. **Automatic durable-page promotion:** rejected because generated report facts must remain advisory until explicitly source-linked and reviewed.
3. **Mass migration from `queries/jinwang-jarvis-*` to `reports/`:** rejected because wiki policy currently tolerates those compatibility paths and writer/link migration needs separate coordination.
4. **Trigger-based live FTS updates:** rejected for the first implementation because explicit rebuild is easier to reason about, test, and roll back.
5. **Raw body linting, rewriting, or normalization:** rejected because `raw/` is immutable evidence.
6. **Writing `_meta/review-queue/` from semantic lint:** rejected because this task is a read-only reporter; queue mutation can be designed later with side-effect budgets.
7. **Adding PyYAML or parser dependencies:** rejected because frontmatter parsing needs only the simple shapes already produced by Jarvis helpers.
8. **Changing unified daily report behavior in this run:** rejected because related files are currently dirty and outside this plan’s minimal integration target.

---

## Implementation readiness

This plan is ready for one subsequent OpenCode implementation run. It has exact file paths, ordered tasks, test targets, rollback steps, and explicit boundaries from the wiki governance, Jarvis runtime/SQLite, and UX/search/report reviewer perspectives.
