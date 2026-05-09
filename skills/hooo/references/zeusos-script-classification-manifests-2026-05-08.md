# ZeusOS script classification manifests — 2026-05-08

Use this reference when continuing ZeusOS repository rearchitecture work that classifies existing scripts without moving or wiring them.

## Pattern

Goal: add declaration-only `legacyScripts` metadata to capability app manifests so scripts get role labels before any migration.

Safe example from `apps/watchdogs/news-center/app.yaml`:

```yaml
legacyScripts:
  - path: scripts/lint_daily_hot_issues_content.py
    role: quality-gate
    migration: classify-only
  - path: scripts/gate_daily_hot_issues_delivery.py
    role: quality-gate
    migration: classify-only
  - path: scripts/render_daily_hot_issues_pdf.py
    role: renderer
    migration: classify-only
```

## Validator contract

`spec.legacyScripts` should be optional. If present:

- it must be a list of mappings;
- `path` must be a repo-relative path under `scripts/`;
- reject absolute paths, `..`, and paths outside `scripts/` such as `../credentials/key.txt`;
- `role` must be one of `watchdog`, `tool`, `renderer`, `quality-gate`, `installer`;
- `migration` must be exactly `classify-only`.

## TDD shape

1. Add a positive test that reads the target manifest via `validate_repo_manifests(paths=ZeusPaths(Path.cwd()))` and asserts the script roles.
2. Add a negative path traversal test with `legacyScripts: [{path: ../credentials/key.txt, ...}]` and expect `ManifestValidationError` mentioning `legacyScripts.*path`.
3. Verify RED before implementation. Expected failures in the first leaf were:
   - `AttributeError: 'AppManifest' object has no attribute 'legacy_scripts'`
   - `Failed: DID NOT RAISE ManifestValidationError`
4. Implement minimally in the declarative manifest loader.
5. Run compileall and targeted regressions.

Known GREEN gate:

```bash
python3 -m compileall -q src/zeus_os/declarative.py tests/test_declarative_manifests.py
PYTHONPATH=src pytest -q tests/test_declarative_manifests.py tests/test_paths.py tests/test_hermes_skill_lifecycle.py
```

Observed result: `22 passed in 0.44s`.

## Commit hygiene

Stage only the manifest/schema/declarative/test files for the leaf. Keep unrelated dirty work out, especially `skills/hooo/SKILL.md`, `src/zeus_os/cli.py`, runtime files, mail-secretary files, `data/`, `state/`, and `credentials/`.

Run staged added-line scans for hardcoded secrets, shell/eval/pickle, and SQL-formatting risks, then request independent staged-diff review before commit.

## Non-claims

Do not claim script migration, cron/systemd changes, runtime wiring, or gateway behavior changes. This is metadata-only classification.