# ZeusOS Repository Rearchitecture — Phase 1 Safety Boundary

> Plain-language checkpoint: this phase did not move the house; it drew the city map, labeled the dangerous rooms, and wrote the contract for the next move.

## Status

- Branch: `feature/zeus-os-repository-rearchitecture`
- Checkpoint date: 2026-05-08
- Current phase: Phase 1 safety boundary complete
- Runtime migration status: not started
- Data/state/credentials migration status: not started

## What is now true

ZeusOS now has a non-destructive Agent OS-style repository frame:

1. Target workspace roots exist for `agents/`, `agent-shim/`, `apps/`, `channels/`, `vmem/`, `journals/`, `wiki/`, `assets/`, `credentials/`, and `workspace/`.
2. Declarative manifests can be validated for agents, shims, apps, and channels.
3. `ZeusPaths` defines the root path policy and blocks implicit creation of sensitive/runtime roots.
4. The manifest validator can use `ZeusPaths` instead of hardcoded paths.
5. `list_registry()` exposes a read-only structured view of registered capabilities.
6. `minerva` declares a compatibility bridge to legacy `skills/hooo` as metadata only.

## Commit chain

```text
8cc7165 docs: scaffold ZeusOS repository rearchitecture
f0a9221 test: add declarative manifest validation
89f1ea3 docs: define aggressive rearchitecture acceptance
594dba5 feat: add ZeusOS root path resolver
a935321 feat: wire manifest validation to ZeusPaths
2205b2d feat: add read-only declarative registry API
087f2e4 feat: declare Minerva HOOO compatibility bridge
```

## Safety boundary

The completed work intentionally avoided the following:

- No movement of `data/` or `state/`.
- No reading, scanning, or committing of `credentials/**` secret values.
- No Hermes core, `~/.hermes`, gateway, systemd, or cron mutation.
- No raw wiki rewrite.
- No runtime caller migration.
- No claim that `hooo` has been moved to `minerva`.

## Current architecture meaning

The current result is a control-plane foundation, not an operational cutover:

| Layer | Current state | Meaning |
|---|---|---|
| Root layout | scaffolded | target OS-style directories exist |
| Manifest validation | implemented | declarations can be checked |
| Path policy | implemented | old/new roots have explicit safety rules |
| Registry API | implemented | capability metadata can be read safely |
| Minerva/HOOO bridge | declared only | future migration contract exists, runtime unchanged |

## Test and review evidence

Leaf-level verification was performed before each committed step:

- Declarative manifest validation: targeted pytest passed after RED/GREEN.
- `ZeusPaths`: resolver tests passed after RED/GREEN.
- Manifest validator + `ZeusPaths`: targeted regression tests passed.
- Read-only registry API: targeted regression tests passed.
- Minerva/HOOO compatibility bridge: targeted regression tests passed.
- Each implementation leaf used staged-diff review and kept unrelated dirty work excluded.

Most recent targeted gate:

```text
PYTHONPATH=src pytest -q tests/test_declarative_manifests.py tests/test_paths.py tests/test_zeus_schema.py
23 passed
```

## Known unrelated dirty work

The following files were present outside this safety-boundary chain and must remain isolated from future rearchitecture commits unless explicitly selected:

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
src/zeus_os/mail_secretary.py
tests/test_mail_secretary.py
```

## Next phase gates

Do not proceed to destructive or runtime migration until a selected next leaf defines its own acceptance, rollback, test, and review gate.

Recommended next choices:

1. **Runtime caller bridge, narrow scope:** one ZeusOS-owned caller reads the Minerva/HOOO compatibility metadata while keeping the legacy fallback.
2. **CLI registry view:** expose `registry list/validate` for operator visibility, but only after isolating existing `cli.py` dirty work.
3. **Migration inventory:** produce a read-only inventory and migration map for `skills/`, `scripts/`, `data/`, and `state/` without moving anything.

## Non-goals for the next step

- Do not move `data/` or `state/`.
- Do not rewrite live cron/systemd/Hermes gateway behavior.
- Do not migrate credentials.
- Do not claim Phase 3 completion until at least one real runtime caller consumes registry metadata with fallback and tests.
