# ZeusOS Rebrand Converged Controller Verdict

Date: 2026-05-06
Controller: Boramae/Hermes
Inputs:
- External lane #1: `01-rebrand-migration-plan/result.md`
- External lane #2: `02-repo-rename-impact-audit/result.md`
- Hermes MoA lanes A/B/C: migration plan, impact audit, adversarial architecture review

## Converged decision
Proceed with a ZeusOS rebrand only as a **compatibility-first product/architecture migration**, not a big-bang repo/package/import/systemd/wiki rename.

The stable taxonomy is:

- **ZeusOS**: product/control-plane/Agent OS identity.
- **Jarvis**: personal-intelligence capability pack inside ZeusOS, plus legacy compatibility name.
- **Hermes**: source-untouched host/gateway/runtime/tool surface.
- **K-Skill/external repos**: independent capability providers connected by adapters/contracts, not vendored.

## Key diff between lanes

### Agreement
All lanes agree on:
- Hermes must remain source-untouched.
- External repos must remain independent via adapter/capability contracts.
- Existing `src/jinwang_jarvis/` and `python -m jinwang_jarvis.cli` are high-blast-radius surfaces.
- Systemd, cron, plugin symlinks, wiki paths, and local config are dangerous rename surfaces.
- Historical `orchestration/` artifacts should not be rewritten.

### Disagreement
External lane #1 is too aggressive in its first PR:
- It proposes `zeus-os` CLI aliases, `src/zeus_os/` shim, and `zeusos-*` unit variants in PR #1.
- It also treats repo rename as Phase 3 and suggests eventual package/import rename.

Hermes MoA + lane #2 converge on a safer first PR:
- PR #1 should be docs/metadata/contract-first, with no runtime behavior changes unless a tiny alias is proven harmless.
- Keep `pyproject.name = "jinwang-jarvis"` initially.
- Keep `src/jinwang_jarvis/` as canonical import namespace for now.
- Do not add active `zeusos-*` systemd aliases yet; alias units can create duplicate/ghost timer risk.

## Accepted first PR scope

Recommended first PR:

`docs: define ZeusOS identity and compatibility migration contract`

Allowed:
- Add `docs/zeus-os-rebrand-migration.md`.
- Add `docs/zeus-os-adapter-contract.md` or a section in the migration doc.
- Update `README.md` top section to say:
  - ZeusOS is the product/control-plane.
  - `jinwang-jarvis` / `jinwang_jarvis` remain compatibility surfaces.
  - Jarvis is the personal-intelligence capability pack.
  - Hermes is source-untouched.
  - External repos are adapter-connected, not vendored.
- Update plugin/Zeus docs wording only if no loader/runtime behavior changes.

Not allowed in PR #1:
- Rename repo.
- Rename `src/jinwang_jarvis/`.
- Rename Python distribution.
- Rename systemd units.
- Move wiki generated paths.
- Change Hermes config or restart gateway.
- Change live DB/artifact paths.
- Touch external skill repos.

## Required gates before any code rename

1. Identity matrix: product/repo/package/import/CLI/systemd/wiki/plugin names classified as keep/alias/deprecate/rename-later.
2. Import/CLI compatibility test plan.
3. Active automation inventory: `systemctl --user list-timers`, cron jobs, plugin symlinks, Hermes config paths.
4. Wiki rename plan with redirects/review queue; no `raw/` mutation.
5. Data backup/rollback for `state/` and `data/` if any path move is proposed.
6. Hermes no-touch verification.

## Controller recommendation

Start with the docs/contract PR. After that, the next code PR should fix pre-existing rename blockers before adding aliases:
- deduplicate Zeus CLI parser drift between `src/jinwang_jarvis/cli.py` and `src/jinwang_jarvis/zeus_os/cli.py` or add regression tests covering both.
- remove hardcoded `/home/jinwang/workspace/jinwang-jarvis` assumptions from tests/defaults where safe.
- make styled voice sample path config/workspace-root driven.

Only after those pass should we introduce `zeusos`/`zeus` aliases.
