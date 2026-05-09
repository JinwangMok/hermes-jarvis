# ZeusOS Rearchitecture — Phase Review after Search/Index Bridge

> Plain-language checkpoint: the new map is now read by two safe readers. One audit caller and one search/index caller can see that Minerva points to legacy Minerva, but the old runtime still has not moved.

## Status

- Branch: `feature/zeus-os-repository-rearchitecture`
- Review date: 2026-05-08
- Current state: declarative metadata is validated and consumed by read-only callers
- Runtime migration status: not started
- Data/state/credentials migration status: not started
- Hermes/gateway/systemd/cron status: unchanged

## Commit chain

```text
8cc7165 docs: scaffold ZeusOS repository rearchitecture
f0a9221 test: add declarative manifest validation
89f1ea3 docs: define aggressive rearchitecture acceptance
594dba5 feat: add ZeusOS root path resolver
a935321 feat: wire manifest validation to ZeusPaths
2205b2d feat: add read-only declarative registry API
087f2e4 feat: declare Minerva Minerva compatibility bridge
f59f28f docs: record rearchitecture phase 1 safety boundary
b68b01a docs: add read-only migration inventory
8acc7b8 feat: consume Minerva bridge in skill lifecycle audit
de7592d docs: record runtime caller bridge checkpoint
ca7f4e1 feat: classify legacy news-center scripts
f654627 docs: record script classification checkpoint
15da48e feat: consume Minerva bridge in skill search index
```

## What is now true

### 1. The repository has an OS-style declarative map

The rearchitecture no longer lives only as intention. It has:

- root layout contracts,
- path policy via `ZeusPaths`,
- manifest validation,
- registry/listing API,
- capability manifests,
- status documents.

### 2. Minerva/Minerva is a validated compatibility bridge

`apps/skill-sets/custom-skills/minerva/app.yaml` declares:

```yaml
compatibilityBridge:
  legacyRoot: skills
  legacyName: minerva
  mode: read-only-metadata
  runtimeWiring: false
```

Important meaning:

- Minerva can point at legacy Minerva metadata.
- Minerva has not been moved.
- Runtime wiring is explicitly false.

### 3. Two read-only callers consume the bridge

| Caller | What it does | Still safe because |
|---|---|---|
| `audit_hermes_skill_lifecycle(..., zeus_paths=...)` | includes `skills/minerva` as compatibility bridge source | audit/read-only only |
| `build_skill_search_index(..., zeus_paths=...)` | indexes `skills/minerva` from Minerva bridge metadata | search/index only; no execution path change |

### 4. Script classification has begun

`news-center` now classifies three legacy scripts:

- `scripts/lint_daily_hot_issues_content.py` → `quality-gate`
- `scripts/gate_daily_hot_issues_delivery.py` → `quality-gate`
- `scripts/render_daily_hot_issues_pdf.py` → `renderer`

All use:

```yaml
migration: classify-only
```

So this is only a label, not a move.

## Safety boundaries still holding

The following are still intentionally untouched:

- `data/` move: not started
- `state/` move: not started
- `credentials/`: not read or migrated
- Hermes core/gateway: unchanged
- systemd/cron: unchanged
- live runtime cutover: not started
- script file moves: not started
- `skills/minerva` physical migration: not started

## Review findings already handled

### Bridge path traversal risk

Earlier review caught that a future caller could be unsafe if metadata allowed:

```yaml
legacyName: ../credentials
```

Fix now enforced:

- `legacyName` must be a single relative name.
- `../...`, absolute paths, and nested paths are rejected.

### Search API compatibility risk

Search/index review caught that changing `skill_roots=[]` semantics would break existing behavior.

Fix now enforced:

- `skill_roots=[]` still falls back to the default Hermes builtin skill root.
- A regression test locks that behavior.
- `zeus_paths` only adds bridge roots; it does not silently remove existing default roots.

## Latest verification evidence

Search/index bridge RED:

```text
TypeError: build_skill_search_index() got an unexpected keyword argument 'zeus_paths'
```

Final GREEN:

```text
30 passed in 3.20s
```

Independent review after fix:

```text
PASS
```

## Current dirty-work isolation

Still unrelated and not part of this rearchitecture checkpoint unless explicitly selected:

```text
skills/minerva/SKILL.md
src/zeus_os/bootstrap.py
src/zeus_os/cli.py
src/zeus_os/runtime.py
tests/test_runtime.py
orchestration/2026-05-07-localhost-architecture-diagram/
orchestration/2026-05-07-mail-preactive-secretary/
scripts/mail-secretary-watchdog.py
skills/minerva/references/zeusos-rearchitecture-leaf-pattern-2026-05-08.md
skills/minerva/references/zeusos-script-classification-manifests-2026-05-08.md
src/zeus_os/mail_secretary.py
tests/test_mail_secretary.py
```

## What is still not claimable

Do not claim any of these yet:

- “Minerva has migrated to Minerva.”
- “ZeusOS runtime is declarative now.”
- “data/state migration is complete.”
- “credentials are handled by the new layout.”
- “CLI operator view is complete.”
- “scripts are moved into apps.”

The accurate claim is narrower:

> ZeusOS has a validated declarative compatibility map, and two read-only callers now consume Minerva/Minerva bridge metadata with legacy fallback preserved.

## Best next gates

### A. Expand script classification

Classify remaining tracked scripts, still without moving them:

- `install.sh`
- `verify.sh`
- `patch_google_workspace_wrapper.py`

Keep `arm-opencode-gateway-recovery.sh` separate because it is gateway-recovery safety-critical.

### B. CLI registry view after dirty isolation

Expose operator visibility such as `registry list/validate`.

Risk:

- `src/zeus_os/cli.py` is dirty, so isolate or clean that first.

### C. Runtime caller bridge hardening doc/tests

Add a small compatibility matrix showing which callers consume registry metadata and which still use legacy roots only.

## Recommendation

Prefer **A: expand script classification** next.

Reason: the architecture now has enough caller proof. More runtime callers would add risk; classification still improves the migration map without touching execution.
