# ZeusOS Rearchitecture — Pre-Merge Review Checklist

> Plain-language checkpoint: before merging, treat this branch like a staged house move. The map and labels can merge only if they stay separate from unrelated runtime/mail work and do not pretend that the real move already happened.

## Scope

- Branch: `feature/zeus-os-repository-rearchitecture`
- Purpose: review/merge readiness checklist for the current declarative rearchitecture chain
- Runtime migration: not started
- Data/state/credentials migration: not started
- Hermes/gateway/systemd/cron changes: out of scope

## Mergeable rearchitecture chain

The intended chain is:

```text
8cc7165 docs: scaffold ZeusOS repository rearchitecture
f0a9221 test: add declarative manifest validation
89f1ea3 docs: define aggressive rearchitecture acceptance
594dba5 feat: add ZeusOS root path resolver
a935321 feat: wire manifest validation to ZeusPaths
2205b2d feat: add read-only declarative registry API
087f2e4 feat: declare Minerva HOOO compatibility bridge
f59f28f docs: record rearchitecture phase 1 safety boundary
b68b01a docs: add read-only migration inventory
8acc7b8 feat: consume Minerva bridge in skill lifecycle audit
de7592d docs: record runtime caller bridge checkpoint
ca7f4e1 feat: classify legacy news-center scripts
f654627 docs: record script classification checkpoint
15da48e feat: consume Minerva bridge in skill search index
39c5fc3 docs: review phase after search index bridge
```

Later script-classification commits may append to this chain if they keep the same safety boundary.

## Merge gate checklist

### 1. Scope gate

- [ ] No Hermes source changes.
- [ ] No gateway/systemd/cron changes.
- [ ] No credentials read, moved, copied, summarized, or committed.
- [ ] No `data/` or `state/` migration.
- [ ] No physical move of `skills/hooo`.
- [ ] No script file move; classification-only metadata is allowed.

### 2. Dirty-work isolation gate

Before merge, confirm these unrelated paths are either excluded or separately resolved:

```text
skills/hooo/SKILL.md
src/zeus_os/bootstrap.py
src/zeus_os/cli.py
src/zeus_os/runtime.py
tests/test_runtime.py
orchestration/2026-05-07-localhost-architecture-diagram/
orchestration/2026-05-07-mail-preactive-secretary/
scripts/mail-secretary-watchdog.py
skills/hooo/references/zeusos-rearchitecture-leaf-pattern-2026-05-08.md
skills/hooo/references/zeusos-script-classification-manifests-2026-05-08.md
src/zeus_os/mail_secretary.py
tests/test_mail_secretary.py
```

These should not be swept into a rearchitecture merge without an explicit separate review.

### 3. Compatibility gate

Required claims that must remain true:

- `legacyName` accepts only a single relative name.
- `../...`, absolute paths, and nested bridge names are rejected.
- `skill_roots=[]` keeps the old Hermes builtin-root fallback.
- `zeus_paths` adds registry-derived compatibility roots; it does not replace existing defaults.
- `runtimeWiring: false` means metadata/index/audit only, not execution.

### 4. Test gate

Minimum test command before merge:

```bash
python3 -m compileall -q src/zeus_os/declarative.py src/zeus_os/paths.py src/zeus_os/hermes_skill_lifecycle.py src/zeus_os/hermes_skill_search.py tests/test_declarative_manifests.py tests/test_paths.py tests/test_hermes_skill_lifecycle.py tests/test_hermes_skill_search.py tests/test_hermes_skill_context.py
PYTHONPATH=src pytest -q tests/test_declarative_manifests.py tests/test_paths.py tests/test_hermes_skill_lifecycle.py tests/test_hermes_skill_search.py tests/test_hermes_skill_context.py
```

A broader suite is useful only if unrelated mail/runtime dirty work is isolated enough to make failures attributable.

### 5. Staged diff safety scan

Run only against intended staged files:

Use the staged-diff safety scan from the `requesting-code-review` skill, but run it only against the intended staged files.

Expected result: no findings.

### 6. Independent review gate

For any code-bearing commit, require an independent staged-diff review with these lenses:

- path traversal/root escape,
- accidental old API behavior changes,
- hidden runtime side effects,
- dirty-file mixing,
- overclaiming migration status.

Docs-only commits can skip full code review but still need staged-file and secret-scan checks.

## Merge narrative

Safe summary for reviewers:

> This branch introduces an OS-style declarative map for ZeusOS and validates it. Minerva can now declare read-only compatibility with legacy HOOO, and two read-only callers consume that metadata for audit and search/index. No runtime cutover, file movement, data/state migration, credentials handling, gateway/systemd/cron change, or HOOO physical migration is included.

## Explicit non-goals

Do not merge this branch as if it completes:

- HOOO-to-Minerva migration,
- runtime declarative execution,
- credentials layout migration,
- data/state migration,
- CLI operator UX,
- gateway restart/recovery changes.

## Recommended next safe leaf

Expand `legacyScripts` classification for simple tracked scripts, still with `migration: classify-only` and no file moves. Keep gateway recovery scripts separate because they are safety-critical.
