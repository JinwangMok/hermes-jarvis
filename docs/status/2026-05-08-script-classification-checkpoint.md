# ZeusOS Rearchitecture — Script Classification Checkpoint

> Plain-language checkpoint: this step did not move scripts. It only put role labels on selected legacy scripts so future migration can be planned safely.

## Status

- Branch: `feature/zeus-os-repository-rearchitecture`
- Checkpoint date: 2026-05-08
- Current phase: declaration-only script classification for `news-center`
- Runtime migration status: not started
- Script move status: not started
- Cron/systemd/gateway status: unchanged

## What changed

The `news-center` capability manifest now names three existing legacy scripts and classifies their roles:

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

This means:

- `lint_daily_hot_issues_content.py` and `gate_daily_hot_issues_delivery.py` are reader-facing quality gates.
- `render_daily_hot_issues_pdf.py` is a renderer.
- All three remain at their legacy `scripts/` paths.
- `migration: classify-only` explicitly says this is metadata, not a move.

## Validation contract

`CapabilityApp` manifests now support optional `legacyScripts` metadata.

Allowed fields:

| Field | Rule |
|---|---|
| `path` | repo-relative path under `scripts/` |
| `role` | one of `watchdog`, `tool`, `renderer`, `quality-gate`, `installer` |
| `migration` | must be `classify-only` |

Rejected examples:

```text
../credentials/key.txt
/absolute/path.py
apps/other/script.py
```

This mirrors the earlier compatibility-bridge hardening: path-like metadata must not escape its intended root.

## What did not change

- No script file was moved.
- No script content was edited.
- No cron job, systemd unit, Hermes gateway, or live runtime wiring was changed.
- `data/`, `state/`, and `credentials/` were not touched.
- The untracked `scripts/mail-secretary-watchdog.py` remained outside this leaf.

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
de7592d docs: record runtime caller bridge checkpoint
ca7f4e1 feat: classify legacy news-center scripts
```

## Verification evidence

TDD RED evidence:

```text
AttributeError: 'AppManifest' object has no attribute 'legacy_scripts'
Failed: DID NOT RAISE ManifestValidationError
```

GREEN gate:

```bash
python3 -m compileall -q src/zeus_os/declarative.py tests/test_declarative_manifests.py
PYTHONPATH=src pytest -q \
  tests/test_declarative_manifests.py \
  tests/test_paths.py \
  tests/test_hermes_skill_lifecycle.py
```

Result:

```text
22 passed in 0.44s
```

Independent staged-diff review:

```text
PASS
```

Static staged scan:

```text
hardcoded secrets: none
shell/eval/pickle/sql risks: none
```

## Dirty-work isolation

The following unrelated dirty work remained outside the committed script-classification leaf and must not be mixed into future rearchitecture commits unless explicitly selected:

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

## Next safe gates

### A. Expand script classification

Classify additional tracked scripts without moving them:

- `scripts/install.sh` as `installer`
- `scripts/verify.sh` as `quality-gate` or `tool`
- `scripts/patch_google_workspace_wrapper.py` as `tool`
- `scripts/arm-opencode-gateway-recovery.sh` only if the safety-sensitive gateway recovery boundary is explicitly acknowledged

### B. Search/index bridge

Make another read-only caller consume existing declarative metadata.

Guardrails:

- Preserve legacy search behavior.
- No writer behavior.
- No runtime execution path change.

### C. CLI registry view after dirty isolation

Expose operator visibility such as `registry list/validate`.

Risk:

- `src/zeus_os/cli.py` is still dirty, so this should wait unless that work is isolated first.

## Current recommendation

Prefer **A: expand script classification**, but skip `arm-opencode-gateway-recovery.sh` unless the gateway recovery boundary is reviewed separately.

Reason: script classification is still low-risk metadata work and improves the migration map without touching runtime execution.
