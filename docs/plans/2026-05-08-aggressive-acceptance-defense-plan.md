# ZeusOS Aggressive Acceptance Defense Plan

> **For Hermes:** This is the review-and-implementation guardrail for pushing repository rearchitecture beyond scaffold into a real declarative Agent OS control plane. Use TDD and independent review before each leaf.

**Goal:** Make the new declarative ZeusOS layout operational, not cosmetic, while preserving runtime truth and Hermes source-untouched boundaries.

**Architecture:** Introduce a compatibility firewall (`zeus_os.paths`) first, connect read-only registry/CLI surfaces second, then connect exactly one runtime caller through the declarative registry with legacy fallback. Legacy roots remain adapters until migration evidence proves they can be retired.

**Tech Stack:** Python, pytest, YAML manifests, current `zeus_os` CLI/runtime, gitignored local runtime/secrets roots.

---

## Aggressive acceptance statement

The **final migration** is accepted only when every migrated ZeusOS-owned capability is registry-driven, app-shaped, compatibility-tested, and rollback-documented. The **next phase exit** is narrower: prove one real runtime caller can read canonical metadata from the declarative registry while old behavior still works.

## Non-negotiable guardrails

- Do not move `data/` or `state/` until inventory + dry-run + rollback + smoke exist.
- Do not touch Hermes source, `~/.hermes`, gateway, cron, systemd, raw wiki, or credentials without separate approval.
- Minerva/Minerva bridge work may not modify `plugins/hermes_*gateway*`, Hermes core, or `~/.hermes`.
- Resolver must be read-only by default. It must not implicitly `mkdir` `credentials`, `data`, `state`, `wiki`, `workspace`, or `vmem`.
- Secret scans inspect staged/tracked declarative files and diffs only; they must not read `credentials/**` values.
- Do not stage unrelated dirty work.
- Do not claim migration success without runtime smoke evidence.

## Review gates for every leaf

1. **Plan gate:** exact files, expected diff scope, tests, rollback/no-op rollback.
2. **RED gate:** new behavior has a failing test before implementation.
3. **GREEN gate:** targeted tests pass and existing targeted regressions still pass.
4. **Safety gate:** staged/tracked declarative diff scan for `api_key`, `secret`, `password`, `token`, `private_key`, `BEGIN .*PRIVATE KEY`; no raw wiki, cron, systemd, gateway, or credential-value reads.
5. **Compatibility gate:** old CLI/path behavior still resolves.
6. **Reviewer gate:** fresh reviewer checks spec compliance + code quality.
7. **Commit gate:** commit only leaf files; pre-existing dirty work remains excluded.

## Root policy model for `zeus_os.paths`

`RootPolicy` must expose at least:

- `name`: logical root name.
- `path`: resolved path.
- `category`: `legacy_runtime | declarative | local_private | generated_asset`.
- `source_of_truth`: `runtime_truth | declarative_truth | compatibility_alias | local_only`.
- `inventory_scannable`: boolean; false for `credentials` and value-bearing runtime stores.
- `implicit_create_allowed`: boolean; false by default.

Typed errors:
- `UnknownRootError` for unsupported root names.
- `MissingRootError` for expected roots that are absent.

Name mapping must be tested explicitly: logical `agent_shim` maps to directory `agent-shim/`.

## Implementation sequence

### Leaf 2.1 — Path contract tests

**Objective:** Lock old/new root semantics before resolver code.

**Files:**
- Create: `tests/test_paths.py`

**Expected diff scope:** tests only.

**Required tests first:**
- `ZeusPaths(Path.cwd()).resolve_root("data") == repo/data`
- legacy roots: `data`, `state`, `skills`, `scripts`.
- declarative roots: `agents`, `agent_shim`, `apps`, `channels`, `vmem`, `journals`, `wiki`, `assets`, `credentials`, `workspace`.
- `data` and `state`: `source_of_truth == "runtime_truth"`.
- `credentials`: `source_of_truth == "local_only"`, `inventory_scannable is False`, `implicit_create_allowed is False`.
- unknown root raises `UnknownRootError`.
- missing required root raises `MissingRootError`; no implicit mkdir.

**RED command:**
```bash
PYTHONPATH=src pytest -q tests/test_paths.py
```
Expected: import/API failure.

**Rollback:** delete `tests/test_paths.py`.

### Leaf 2.2 — Minimal `zeus_os.paths` resolver

**Objective:** Implement only Leaf 2.1 API.

**Files:**
- Create: `src/zeus_os/paths.py`
- Modify: `tests/test_paths.py` only for genuine test bug, not weaker assertions.

**Expected diff scope:** one source file + path tests.

**GREEN command:**
```bash
python3 -m compileall -q src/zeus_os/paths.py tests/test_paths.py
PYTHONPATH=src pytest -q tests/test_paths.py tests/test_declarative_manifests.py tests/test_zeus_schema.py
```

**Rollback:** delete `src/zeus_os/paths.py`; restore `tests/test_paths.py` if adjusted.

### Leaf 2.3a — Validator accepts `ZeusPaths`

**Objective:** Let manifest validation receive a resolver without changing validation behavior.

**Files:**
- Modify: `src/zeus_os/declarative.py`
- Modify: `tests/test_declarative_manifests.py`

**Test:** `test_validate_repo_manifests_accepts_zeus_paths`.

**Expected RED:** validator rejects `ZeusPaths` object.

**Verification:**
```bash
PYTHONPATH=src pytest -q tests/test_declarative_manifests.py::test_validate_repo_manifests_accepts_zeus_paths
```

**Rollback:** revert the two-file diff.

### Leaf 2.3b — Registry listing API

**Objective:** Return app/channel/agent names and manifest objects through a read-only registry API.

**Files:**
- Modify: `src/zeus_os/declarative.py`
- Modify: `tests/test_declarative_manifests.py`

**Test:** `test_declarative_registry_lists_agents_apps_and_channels`.

**Acceptance:** includes `boramae`, `news-center`, `minerva`, `discord`; no filesystem writes.

**Rollback:** revert the two-file diff.

### Leaf 2.3c — Operational entrypoint validation

**Objective:** Remove placeholder loophole from runtime acceptance.

**Files:**
- Modify: `docs/schemas/capability-app.schema.yaml`
- Modify: relevant `app.yaml` sample manifests if lifecycle field is added.
- Modify: `src/zeus_os/declarative.py`
- Modify: `tests/test_declarative_manifests.py`

**Rule:** `spec.lifecycle` is required and must be `placeholder | operational`. Placeholder apps are valid declarations but excluded from runtime-success claims. Operational apps must have an existing executable/module/documented entrypoint according to their kind.

**Tests:**
- `test_placeholder_apps_do_not_count_as_runtime_operational`
- `test_operational_app_requires_resolvable_entrypoint`

**Rollback:** revert schema, manifest, validator, and test changes.

### Leaf 2.4a — Read-only CLI valid case

**Objective:** Expose manifest validation as operator read-only command.

**Files:**
- Modify: `src/zeus_os/cli.py`
- Create or modify: `tests/test_cli_repo_validate_manifests.py`

**Command:**
```bash
PYTHONPATH=src python3 -m zeus_os.cli repo validate-manifests --repo-root .
```

**Test:** valid repo exits `0`, stdout includes validated agent/app/channel counts, no files created.

**Rollback:** revert CLI/test diff.

### Leaf 2.4b — Read-only CLI invalid case

**Objective:** CLI reports invalid manifests without writing artifacts.

**Files:**
- Modify: `tests/test_cli_repo_validate_manifests.py`
- Modify: `src/zeus_os/cli.py` only if needed.

**Test:** temp repo with bad app kind exits non-zero and stderr names `ManifestValidationError` or a user-readable equivalent.

**Rollback:** revert CLI/test diff.

### Leaf 2.5a — Minerva read-only discovery bridge

**Objective:** Make Minerva/Minerva metadata discoverable through `apps/skill-sets/custom-skills/minerva/app.yaml` without changing runtime execution.

**Allowed files:**
- `src/zeus_os/declarative.py`
- `tests/test_declarative_manifests.py` or a new focused test
- `apps/skill-sets/custom-skills/minerva/app.yaml`

**Forbidden files:**
- `plugins/hermes_*gateway*`
- Hermes core or `~/.hermes`
- cron/systemd files
- `data/`, `state/` contents

**Tests:**
- old `skills/minerva` remains discoverable as compatibility location through resolver.
- `minerva` manifest returns canonical metadata and points to compatibility alias, not moved files.

**Rollback:** revert allowed-file diff only.

### Leaf 2.5b — Existing skill lifecycle caller consumes Minerva bridge with fallback

**Objective:** A concrete ZeusOS-owned runtime caller reads Minerva metadata through registry first, then falls back to legacy `skills/minerva`/Hermes skill roots.

**Exact caller:**
- Modify: `src/zeus_os/hermes_skill_lifecycle.py`
  - `_skill_roots(...)` may append a registry-derived Minerva compatibility root/metadata source.
  - `_find_skill_dir(...)` remains the fallback resolver for legacy skill dirs.
  - `audit_hermes_skill_lifecycle(...)` must expose whether a skill was discovered from declarative registry metadata or legacy roots.
- Modify: `tests/test_hermes_skill_lifecycle.py`
  - add `test_audit_skill_lifecycle_prefers_minerva_registry_metadata_with_legacy_minerva_fallback`.

**Forbidden files:**
- `plugins/hermes_*gateway*`
- Hermes core or `~/.hermes`
- cron/systemd files
- `data/`, `state/` contents

**Acceptance:**
- Test proves registry-first behavior for `apps/skill-sets/custom-skills/minerva/app.yaml` metadata.
- Test proves legacy `skills/minerva/SKILL.md` remains usable when registry metadata is absent or placeholder-only.
- Existing lifecycle tests still pass:
```bash
PYTHONPATH=src pytest -q tests/test_hermes_skill_lifecycle.py tests/test_declarative_manifests.py tests/test_paths.py
```
- Minerva status smoke remains unchanged:
```bash
PYTHONPATH=src python3 -m zeus_os.cli minerva status --config config/pipeline.local.yaml --run-id minerva-20260508-1d0b544b5090
```

**Rollback:** revert `src/zeus_os/hermes_skill_lifecycle.py` and `tests/test_hermes_skill_lifecycle.py` changes only.

### Leaf 2.6a — Sanitized inventory API dry-run

**Objective:** Inventory candidate migration files without moving or reading secret values.

**Files:**
- Create: `src/zeus_os/inventory.py`
- Create: `tests/test_inventory.py`

**Scope:** `skills/`, `scripts/`, and metadata-only stats for selected `data/`/`state/` paths: names, types, sizes/counts when safe; no contents for runtime DB/artifact values.

**Tests:** redaction, no file moves, no `credentials/**` value reads, deterministic output.

**Rollback:** delete inventory source/test files.

### Leaf 2.6b — Sanitized inventory report

**Objective:** Emit a tracked sanitized markdown report only if it contains no secrets; otherwise write ignored artifact and tracked summary.

**Files:**
- Create: `docs/plans/2026-05-08-zeus-os-migration-inventory.md` only after secret scan passes.

**Verification:** staged diff secret scan + reviewer safety PASS.

**Rollback:** delete generated report or move to ignored artifact.

## Current recommended next action

Start with **Leaf 2.1 + 2.2 only**. Do not begin Minerva/Minerva bridge until the path resolver and registry read-only surfaces pass review.
