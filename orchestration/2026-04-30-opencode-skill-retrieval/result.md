# Hermes Skill Retrieval Sidecar Result

## Changed files

- `src/jinwang_jarvis/hermes_skill_search.py` — new Jarvis-owned Hermes skill FTS5 sidecar with safe SKILL.md frontmatter parsing, secret redaction before persistence/indexing, content-hash incremental indexing, usage metadata ingestion, and deterministic composite scoring.
- `src/jinwang_jarvis/hermes_skill_context.py` — new budget-aware skill context generator built on search results.
- `src/jinwang_jarvis/cli.py` — added `hermes-skill-search-index`, `hermes-skill-search`, and `hermes-skill-context` commands.
- `tests/test_hermes_skill_search.py` — coverage for relevance, incremental update, secret redaction, pinned boost, negative-claim penalty, usage/recency scoring, and CLI JSON.
- `tests/test_hermes_skill_context.py` — coverage for context budget and CLI JSON.
- `orchestration/2026-04-30-opencode-skill-retrieval/result.md` — this artifact.

## Commands run

- `git status --short --untracked-files=all` before edits and after verification.
- `PYTHONPATH=src pytest tests/test_hermes_skill_search.py tests/test_hermes_skill_context.py`
  - First run: 8 passed, 1 failed due to a test fixture rewrite bug (`Path.mkdir` without `exist_ok=True`).
  - Final run: 9 passed.
- `lsp_diagnostics` on:
  - `src/jinwang_jarvis/hermes_skill_search.py`
  - `src/jinwang_jarvis/hermes_skill_context.py`
  - `src/jinwang_jarvis/cli.py`
  - `tests/test_hermes_skill_search.py`
  - `tests/test_hermes_skill_context.py`
- Manual CLI smoke test using a tmp_path SKILL.md fixture:
  - `python -m jinwang_jarvis.cli hermes-skill-search-index --db <tmp>/skills.sqlite --skill-root <tmp>/skills`
  - `python -m jinwang_jarvis.cli hermes-skill-search --db <tmp>/skills.sqlite --query "smoke retrieval" --top-k 1 --format json`
  - `python -m jinwang_jarvis.cli hermes-skill-context --db <tmp>/skills.sqlite --query "smoke retrieval" --budget 160 --format json`

## Test outcomes

- OpenCode targeted pytest: `9 passed in 1.09s`.
- Boramae controller re-run: `PYTHONPATH=src pytest tests/test_hermes_skill_search.py tests/test_hermes_skill_context.py -q` → `9 passed in 1.16s`.
- Boramae controller full suite: `PYTHONPATH=src pytest -q` → `197 passed in 156.89s`.
- LSP diagnostics: no diagnostics found for all modified Python source/test files after cleanup.
- Manual CLI smoke output confirmed:
  - index command inserted 1 skill and returned `ok: true`.
  - search command returned the `manual-cli` skill for `smoke retrieval` with JSON-serializable fields.
  - context command returned one snippet and `estimated_tokens: 92` within the `budget_tokens: 160` limit.
- Boramae controller real-corpus smoke indexed `/home/jinwang/.hermes/skills` with `inserted: 159`, confirming the sidecar runs against the local skill corpus.

## Protected/unrelated files

The following files were already dirty before this run and remained unrelated/protected; they were not edited by this implementation:

- `scripts/lint_daily_hot_issues_content.py`
- `src/jinwang_jarvis/unified_daily_report.py`
- `tests/test_daily_hot_issues_content_quality.py`
- `tests/test_unified_daily_report.py`

No changes were made under `/home/jinwang/.hermes/hermes-agent`, and no gateway restart, credentials access, or unrelated dirty-file edits were performed.

## Remaining risks

- Scoring weights are deterministic and covered by focused tests, but production relevance may still need tuning after real Hermes skill corpus usage.
- FTS5 availability depends on the host SQLite build; the index command returns a clear `fts5_unavailable` result if unavailable.
