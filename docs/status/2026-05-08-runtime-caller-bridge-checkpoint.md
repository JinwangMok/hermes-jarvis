# ZeusOS Rearchitecture — Runtime Caller Bridge Checkpoint

> Plain-language checkpoint: the map is no longer just on paper. One ZeusOS-owned read-only caller now looks at the Minerva/HOOO bridge contract, but it still does not move the old HOOO runtime.

## Status

- Branch: `feature/zeus-os-repository-rearchitecture`
- Checkpoint date: 2026-05-08
- Current phase: first read-only runtime caller bridge complete
- Runtime migration status: not started
- Operational cutover status: not started
- Data/state/credentials migration status: not started

## What changed in this checkpoint

The `minerva` manifest already declared this compatibility contract:

```yaml
compatibilityBridge:
  legacyRoot: skills
  legacyName: hooo
  mode: read-only-metadata
  runtimeWiring: false
```

This checkpoint made one ZeusOS-owned caller consume that metadata:

```python
audit_hermes_skill_lifecycle(..., zeus_paths=ZeusPaths(repo_root))
```

When `zeus_paths` is provided, the audit can now discover the declarative `minerva -> skills/hooo` bridge and include the legacy HOOO skill as a `compatibility_bridge` source in the audit result.

## What did not change

This is intentionally not a runtime migration:

- `skills/hooo` was not moved.
- HOOO execution still uses the existing legacy runtime path.
- Hermes core, gateway, systemd, cron, and `~/.hermes` were not changed.
- `data/`, `state/`, and `credentials/` were not moved or rewritten.
- No external service call or live gateway restart was performed.

## Commit chain extension

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
```

## Architecture meaning

| Layer | Before | Now | Still not true |
|---|---|---|---|
| Path policy | `ZeusPaths` existed | caller can receive `ZeusPaths` | no global path rewrite |
| Registry metadata | readable | consumed by one caller | not consumed everywhere |
| Minerva/HOOO bridge | declared only | audit reads it | HOOO not moved to Minerva |
| Runtime truth | legacy roots | unchanged | no `data/state` migration |

## Safety fix from review

Independent review found a real boundary risk:

```yaml
legacyName: ../credentials
```

If accepted, a future caller could join that value with `skills/` and accidentally inspect outside the intended compatibility root.

The fix is now part of declarative validation:

- `legacyName` must be a single relative name.
- Rejected examples include `../credentials`, `/absolute/path`, and `a/b`.
- This keeps the compatibility bridge inside the `skills/` root contract.

## Verification evidence

Targeted RED/GREEN evidence was captured during the leaf:

```text
RED 1: TypeError: audit_hermes_skill_lifecycle() got an unexpected keyword argument 'zeus_paths'
RED 2: Failed: DID NOT RAISE ManifestValidationError
GREEN: 20 passed in 0.45s
```

Final targeted gate:

```bash
python3 -m compileall -q \
  src/zeus_os/declarative.py \
  src/zeus_os/hermes_skill_lifecycle.py \
  tests/test_declarative_manifests.py \
  tests/test_hermes_skill_lifecycle.py

PYTHONPATH=src pytest -q \
  tests/test_declarative_manifests.py::test_compatibility_bridge_legacy_name_cannot_escape_skills_root \
  tests/test_hermes_skill_lifecycle.py::test_audit_hermes_skill_lifecycle_consumes_minerva_hooo_registry_bridge \
  tests/test_hermes_skill_lifecycle.py \
  tests/test_declarative_manifests.py \
  tests/test_paths.py
```

Result:

```text
20 passed
```

Independent staged-diff review result:

```text
PASS
```

## Dirty-work isolation

The following unrelated dirty work remained outside the committed bridge leaf and must not be mixed into future rearchitecture commits unless explicitly selected:

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

## Next safe gates

### A. Search/index bridge

Make `hermes_skill_search` or another read-only search/index caller consume the same bridge metadata.

Guardrails:

- TDD first.
- No writer behavior.
- No runtime execution change.
- Preserve legacy search behavior.

### B. CLI registry view after dirty isolation

Expose operator visibility such as `registry list/validate`.

Risk:

- `src/zeus_os/cli.py` is dirty, so this should wait unless the CLI dirty work is isolated first.

### C. Script classification manifests

Add declaration-only script classifications for news-center/email-handler/tool scripts without moving scripts.

Guardrails:

- No script move.
- No cron/systemd/gateway change.
- Only metadata and validation.

## Current recommended next step

Prefer **A: Search/index bridge** if the goal is to keep proving declarative metadata is operationally consumed.

Prefer **C: Script classification manifests** if the goal is to keep risk low and continue expanding the declarative map before touching more callers.
