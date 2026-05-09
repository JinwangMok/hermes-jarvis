# ZeusOS rearchitecture: pre-merge gate + repository-ops script classification (2026-05-08)

Use this reference when continuing the ZeusOS repository rearchitecture chain after the Minerva/Minerva bridge and initial script classification leaves.

## Session pattern

Jinwang requested `C -> A`:

1. **C: PR/merge review system** — add a checkpoint document before doing more implementation.
2. **A: additional script classification** — classify more tracked scripts without moving them.

This sequencing is important: close a review/checkpoint gate before expanding another declarative leaf.

## Pre-merge checklist leaf

Committed document:

```text
docs/status/2026-05-08-pre-merge-review-checklist.md
924a9ea docs: add pre-merge review checklist
```

The checklist captured:

- mergeable rearchitecture commit chain,
- dirty-work isolation gate,
- compatibility gate,
- test gate,
- independent review gate,
- explicit non-goals: no Minerva migration claim, no runtime cutover, no data/state/credentials migration, no gateway/systemd/cron changes.

### Pitfall found

A docs-only checklist included literal grep commands for staged secret/static scans. The checklist's own added lines matched the scan regex (`secret`, `token`, etc.), creating a false positive.

Fix: for future status/checklist docs, prefer a pointer such as:

```text
Use the staged-diff safety scan from the `requesting-code-review` skill, but run it only against the intended staged files.
```

instead of embedding full grep patterns in the newly staged document.

## Repository-ops script classification leaf

Committed manifest:

```text
apps/repository-ops/app.yaml
bd3cda5 feat: classify repository ops scripts
```

Classified tracked scripts only:

```yaml
legacyScripts:
  - path: scripts/install.sh
    role: installer
    migration: classify-only
  - path: scripts/verify.sh
    role: quality-gate
    migration: classify-only
  - path: scripts/patch_google_workspace_wrapper.py
    role: tool
    migration: classify-only
```

Excluded intentionally:

```text
scripts/arm-opencode-gateway-recovery.sh
scripts/mail-secretary-watchdog.py
```

Reason:

- `arm-opencode-gateway-recovery.sh` is Hermes gateway recovery safety-critical and should get a separate gate.
- `mail-secretary-watchdog.py` was untracked/dirty and should not be swept into rearchitecture classification.

## TDD/verification evidence

RED:

```text
KeyError: 'repository-ops'
```

GREEN:

```text
38 passed in 2.94s
```

Independent review:

```text
PASS
```

## Reusable guidance

For future ZeusOS rearchitecture leaves:

1. If the user gives chained choices like `C->A`, execute them in order and commit each concern separately.
2. For docs-only gates, scan staged diff but avoid embedding literal scan regexes that self-trigger.
3. For script classification, add manifest metadata only; never move scripts or change runtime wiring.
4. Keep safety-critical gateway recovery scripts in a separate explicitly reviewed classification gate.
5. Keep untracked/dirty mail/runtime work out of rearchitecture commits unless the user explicitly selects that concern.
