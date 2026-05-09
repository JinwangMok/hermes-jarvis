# ZeusOS Rebrand Migration Contract

**Status:** compatibility-first contract
**Date:** 2026-05-07
**Scope:** product and architecture identity for `zeus-os` becoming ZeusOS without a big-bang rename

## Executive decision

`zeus-os` should evolve into **ZeusOS** as the product/control-plane identity, but the first migration step is **not** a repository, package, import, systemd, wiki, or database rename.

The first step is to freeze the compatibility contract so future implementation work can proceed without breaking Hermes, local automation, generated wiki paths, or external skill repositories.

## Identity taxonomy

| Name | Meaning | Current handling |
|---|---|---|
| **ZeusOS** | Product identity and Agent OS/control-plane architecture | Forward-facing product/control-plane name |
| **ZeusOS** | Personal-intelligence capability pack: mail, calendar, briefings, hot issues, opportunity radar, Minerva/Minerva | Retained as a capability-pack and legacy compatibility name |
| **`zeus-os`** | Existing repository/distribution/local workspace identity | Compatibility surface; do not rename in the first PR |
| **`zeus_os`** | Existing Python import namespace | Compatibility surface; keep canonical until aliases are proven |
| **Hermes** | Upstream host/gateway/runtime/tool surface | Source-untouched; integrated only by plugins, configs, sidecars, and CLI boundaries |
| **Portable experience artifacts** | Browser harness helpers, URL/selector recipes, SKILL.md playbooks, and learned skip-step knowledge | Reusable ZeusOS knowledge/artifact layer; canonical only when registered in SQLite plus artifacts |
| **External repos** | K-Skill and other independently maintained capability providers | Stay independent; connect through adapter contracts, not vendoring |

## Non-negotiable invariants

1. **Hermes source remains untouched.** ZeusOS may provide Hermes plugins, systemd templates, sidecars, and CLI-facing adapters, but it must not patch Hermes core.
2. **SQLite + filesystem artifacts remain canonical for ZeusOS state.** Discord, A2A, markdown, and reports are projections.
3. **ZeusOS is not erased.** It becomes the personal-intelligence capability pack inside ZeusOS.
4. **External repos are not absorbed.** K-Skill and similar repos keep their own source of truth and lifecycle.
5. **No big-bang rename.** Rename surfaces must be classified, tested, and migrated with rollback.
6. **Generated wiki paths are not canonical just because they exist.** They follow the wiki generated-report contract and should not be moved without a planned writer migration.
7. **Learned browser recipes are portable contracts, not runtime renames.** ZeusOS may capture browser-harness URL patterns, selectors, helper recipes, and skip-step knowledge as reusable artifacts or skills, but this must not rename code, patch Hermes, vendor external repos, or make generated reports canonical.

## First PR scope

The first safe PR is documentation/contract-first:

```text
docs: define ZeusOS identity and compatibility migration contract
```

Allowed:
- add this migration contract;
- add an external adapter contract document;
- update README identity language;
- update wording in existing ZeusOS docs if it does not change runtime behavior.

Not allowed in the first PR:
- repository rename;
- `pyproject.toml` distribution rename;
- `src/zeus_os/` package rename;
- `python -m zeus_os.cli` removal;
- systemd unit rename or alias unit activation;
- Hermes config changes or gateway restart;
- live DB/artifact movement;
- generated wiki path movement;
- external skill repository edits.

## Rename surface matrix

| Surface | First-step decision | Why |
|---|---|---|
| GitHub repository | Keep existing remote names | Avoid clone/automation churn before compatibility gates |
| Python distribution `zeus-os` | Keep | Plugin requirements and installs may depend on it |
| Import namespace `zeus_os` | Keep | Tests, plugins, docs, and scripts depend on it |
| CLI `python -m zeus_os.cli` | Keep | Existing docs/systemd/skills use it |
| Zeus subcommand | Keep and document | `python -m zeus_os.cli zeus ...` is the current safe ZeusOS entrypoint |
| systemd units `zeus-os-*` | Keep | Renaming can create ghost timers or duplicate schedules |
| `hermes-gateway.service` | Never rename as ZeusOS | It is the Hermes host/gateway boundary |
| Wiki `queries/zeus-os-*` paths | Keep until writer migration | Generated reports and indexes rely on stable paths |
| `state/` and `data/` artifacts | Keep | Avoid SQLite/data split-brain |
| Historical `orchestration/` artifacts | No-touch | Evidence records should not be rewritten |

## Hermes profile stance

Hermes profiles are a strong fit for ZeusOS, but they are a **runtime-operations boundary**, not a code rename boundary and not a security sandbox.

Recommended first experiment:

- keep `default` / Boramae as Jinwang's main orchestrator profile;
- create a separate `zeus-os` Hermes profile for mail, calendar, news, and recurring report delivery;
- keep KARVIS, contractor, and voice profiles as later candidates after the ZeusOS split is proven;
- use profile-specific configs, sessions, skills, memory, models, and gateway services to reduce context pollution and single-gateway queue contention;
- treat filesystem/security isolation separately through `terminal.cwd`, Docker/SSH backends, or separate Unix users when real containment is required.

This profile split must remain compatibility-first: it may add a ZeusOS-owned profile/gateway deployment path, but it must not rename the repository, Python package, existing CLI, systemd units, wiki paths, or Hermes source in the first PR.

## Gates before aliases, profiles, or renames

Before adding `zeusos` import/CLI aliases, introducing additional Hermes gateway profiles, or renaming any service/path, complete these gates:

1. **Identity matrix:** classify every surface as keep, alias, deprecate, profile-split, or rename-later.
2. **Import/CLI test plan:** prove old and new paths work together before deprecating anything.
3. **Zeus CLI parser drift check:** remove or regression-test duplicated parser definitions between `src/zeus_os/cli.py` and `src/zeus_os/zeus_os/cli.py`.
4. **Path-hardcoding audit:** remove unsafe `/home/jinwang/workspace/zeus-os` assumptions from tests/defaults where feasible.
5. **Active automation inventory:** list user systemd timers/services, Hermes cron jobs, plugin symlinks, and config paths before systemd or repo path changes.
6. **Data backup/rollback:** backup `state/` and `data/` before any path migration.
7. **Wiki migration plan:** queue durable wiki entity/concept changes and generated-path movement separately; never rewrite `raw/`.
8. **Hermes no-touch verification:** verify no files under Hermes source changed.
9. **Portable recipe provenance:** before promoting learned browser recipes or `SKILL.md` playbooks as reusable ZeusOS assets, record their source task, target site/app boundary, selector fragility, artifact path, verification status, and last-known-good timestamp.

## Recommended phased roadmap

### Phase 0 — Contract freeze
Document ZeusOS identity, ZeusOS capability-pack status, Hermes source-untouched boundary, external adapter stance, no-touch surfaces, and the portable browser-recipe/skill artifact stance.

### Phase 1 — Rename-blocker cleanup
Fix architectural blockers that make aliases unsafe:
- Zeus CLI parser drift;
- hardcoded local workspace path assumptions;
- styled-voice sample path default should become config/workspace-root driven.

### Phase 2 — Additive aliases
Only after tests pass, add narrow aliases such as a `zeusos` CLI entrypoint or `zeus_os` import shim while keeping existing names working.

### Phase 3 — Operator migration
Inventory active timers/cron/plugins, then migrate systemd or filesystem names only with disable-old/enable-new/rollback scripts.

### Phase 4 — Wiki and public rename
Promote `entities/zeusos.md` and related concepts after implementation names are stable. Move generated paths only after writers are updated.

## Compatibility promise

Until a later gate explicitly changes this document, all existing operator commands should remain valid, including:

```bash
PYTHONPATH=src python3 -m zeus_os.cli zeus init
PYTHONPATH=src python3 -m zeus_os.cli collect-mail --config config/pipeline.local.yaml
```

ZeusOS is therefore the new product/control-plane identity, while `zeus-os` and `zeus_os` remain compatibility surfaces during the transition.
