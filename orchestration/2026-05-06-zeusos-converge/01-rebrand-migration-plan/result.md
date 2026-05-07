# ZeusOS Rebrand / Migration Plan

**Status:** Draft — awaiting Jinwang review before execution  
**Date:** 2026-05-06  
**Owner:** External contractor lane #1 (Sisyphus)  
**Scope:** jinwang-jarvis → ZeusOS product/control-plane rebrand  
**Constraint:** Read-only analysis; no production source edits under this lane  

---

## 1. Executive Recommendation

**Promote `jinwang-jarvis` to `ZeusOS`** — the canonical repository and product identity for Jinwang's personal Agent OS / control-plane. Do not fork or create a new repo. The existing repo already contains:

- A mature mail/calendar intelligence pipeline (the original "Jarvis" capability pack)
- A fully-designed Zeus OS control plane (`src/jinwang_jarvis/zeus_os/`, docs, operator guide)
- Hermes integration plugins (`plugins/hermes_*`)
- Skills, systemd units, CLI surface, tests, and operational documentation

**The rebrand is therefore a naming/identity migration, not an architectural rebuild.** The primary work is:
1. Establishing backward-compatible aliases so nothing breaks during transition
2. Gradually migrating naming surfaces (CLI, docs, systemd, wiki) without a big-bang rename
3. Keeping Hermes source-untouched and external repos independent

**Decision:** Proceed with a phased, gated migration. Do not rename the GitHub repo until Phase 3.

---

## 2. Architecture / Product Identity Decision

### 2.1 Identity Model

| Layer | Identity | Role |
|-------|----------|------|
| **Repository** | `ZeusOS` (renamed from `jinwang-jarvis`) | Canonical source-of-truth for the Agent OS |
| **Product** | `ZeusOS` | Personal Agent OS / control-plane |
| **Capability Pack** | `Jarvis` | Personal-intelligence module (mail, calendar, briefing, radar) living *inside* ZeusOS |
| **Upstream Runtime** | `Hermes` | Source-untouched gateway / tool host / Discord runtime |
| **External Repos** | `K-Skill`, etc. | Independent; integrated via versioned adapter contracts |

### 2.2 Boundary Map

```
┌─────────────────────────────────────────────────────────────┐
│  ZeusOS (this repo)                                         │
│  ├── zeus_os/          ← Agent OS control plane (core)      │
│  ├── jinwang_jarvis/   ← Jarvis capability pack (legacy pkg)│
│  ├── plugins/          ← Hermes gateway adapters            │
│  ├── skills/           ← OMC / Hermes skills                │
│  ├── systemd/          ← Service templates                  │
│  └── docs/             ← Operator guides                    │
├─────────────────────────────────────────────────────────────┤
│  Hermes (external, source-untouched)                        │
│  ├── hermes-agent/     ← Gateway runtime                    │
│  ├── skills/           ← Hermes canonical skill registry    │
│  └── plugins/          ← Loaded from ZeusOS symlinks        │
├─────────────────────────────────────────────────────────────┤
│  External Repos (independent)                               │
│  ├── K-Skill/          ← Versioned adapter contract         │
│  └── ...               ← CLI boundary, not vendored         │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Key Architectural Commitments

1. **Hermes remains source-untouched.** All integration lives in ZeusOS modules, plugins, and systemd templates.
2. **SQLite + artifacts are canonical.** Discord, A2A, markdown, and dashboards are projections.
3. **One Discord bot for MVP.** Personas are DB `agent_cards`, not separate bot accounts.
4. **External repos are not vendored.** Integration is through versioned adapter contracts, CLI boundaries, and artifact/event projections.

---

## 3. Phased Migration Plan (No Big-Bang Rename)

### Phase 0: Foundation (Complete)
- Zeus OS control plane implemented: `src/jinwang_jarvis/zeus_os/`
- Schema, boardroom, task queue, worker model, A2A projection, painter workflow
- Docs: `docs/zeus-os-final-implementation-plan.md`, `docs/zeus-os-operator-guide.md`, `docs/zeus-os-usage-guide.md`
- Plugin: `plugins/hermes_zeus_gateway/`

### Phase 1: Compatibility Layer + Alias Surface (Target: PR #1)
**Goal:** Allow the codebase to answer to both `jinwang-jarvis` and `zeus-os` without breaking any existing automation.

**Actions:**
- [ ] Add `zeus-os` CLI alias alongside `jinwang-jarvis` (argparse `prog` fallback)
- [ ] Add `zeus` top-level CLI command as alias for `jinwang-jarvis zeus` (already exists)
- [ ] Create `src/zeus_os/` compatibility re-export package that wraps `src/jinwang_jarvis/`
- [ ] Update `pyproject.toml`:
  - Add `zeus-os` console script entry point (alias to `jinwang-jarvis`)
  - Keep `jinwang-jarvis` entry point
  - Add package alias metadata
- [ ] Add systemd unit template variants with `zeusos-*` names that symlink to `jinwang-jarvis-*` units
- [ ] Update `scripts/install.sh` to accept `--product-name=zeusos` flag (default remains `jinwang-jarvis`)
- [ ] Add backward-compat shim in `runtime.py` for service name generation
- [ ] Update `README.md` with dual-branding header: "ZeusOS (formerly Hermes Jarvis)"

**Non-actions (Phase 1):**
- Do NOT rename `src/jinwang_jarvis/` directory yet
- Do NOT rename GitHub repo yet
- Do NOT change any import paths in tests
- Do NOT modify existing systemd units in production

### Phase 2: Documentation + Wiki Convergence (Target: PR #2)
**Goal:** Establish ZeusOS as the primary public-facing identity while preserving Jarvis as a capability-pack name.

**Actions:**
- [ ] Rename `docs/` files:
  - `docs/zeus-os-*.md` → consolidate into `docs/zeusos/` directory
  - Keep `docs/public-guide.*.md` but update references
- [ ] Update all `README.md` examples to show `zeus-os` CLI first, with `jinwang-jarvis` as "legacy alias" note
- [ ] Update `docs/cron.md` to reference `zeusos` service names
- [ ] Update `docs/productized-jarvis.*.md` → `docs/productized-zeusos.*.md` (or add redirects)
- [ ] Wiki changes (after code decisions finalized):
  - Create `entities/zeusos.md` as canonical entity page
  - Update `entities/jinwang-jarvis.md` to note legacy/compatibility status
  - Add `concepts/zeusos-as-hermes-enhancement-layer.md`
  - Add wikilinks and index entries
  - Append compact log entry

### Phase 3: Production Rename with Rollback (Target: PR #3)
**Goal:** Execute the full rename with a tested rollback path.

**Actions:**
- [ ] Rename GitHub repository `JinwangMok/jinwang-jarvis` → `JinwangMok/zeus-os`
  - GitHub automatically redirects `jinwang-jarvis` URLs
  - Update local remotes (`git remote set-url origin`)
- [ ] Rename Python package: `src/jinwang_jarvis/` → `src/zeus_os/`
  - Add backward-compat shim: `src/jinwang_jarvis/__init__.py` re-exports from `zeus_os`
  - Update all imports in tests to use `zeus_os` (keep `jinwang_jarvis` shim for external consumers)
- [ ] Rename CLI: `jinwang-jarvis` → `zeus-os` (primary), `jinwang-jarvis` becomes alias
- [ ] Rename systemd units:
  - `jinwang-jarvis-cycle.*` → `zeusos-cycle.*`
  - `jinwang-jarvis-weekly-review.*` → `zeusos-weekly-review.*`
  - `jinwang-jarvis-hermes-health.*` → `zeusos-hermes-health.*`
  - Keep old units disabled but present as migration fallback
- [ ] Update `pyproject.toml`:
  - `name = "zeus-os"`
  - Keep `jinwang-jarvis` as extra dependency / alias package
- [ ] Update `config/pipeline.yaml`: `project_name: zeus-os`
- [ ] Update all state/database paths:
  - `state/jarvis.sqlite3` → `state/zeusos.sqlite3` (or keep with symlink)
  - `state/personal_intel.db` remains (data file, not identity-bearing)
- [ ] Update `bin/` scripts to use `zeus-os` module path
- [ ] Update plugins:
  - `plugins/hermes_zeus_gateway/` — already named correctly
  - `plugins/hermes_hooo_gateway/` — update description
  - `plugins/hermes_jarvis_styled_voice_gateway/` → `plugins/hermes_zeusos_styled_voice_gateway/`

**Rollback Plan:**
- GitHub repo rename is reversible within a short window
- Python package shim allows `import jinwang_jarvis` to continue working
- systemd units: old units remain disabled; `systemctl --user enable zeusos-cycle.timer` can be reversed
- Database files: symlink old → new names during transition

### Phase 4: External Repo Adapter Contracts (Target: PR #4)
**Goal:** Formalize how K-Skill and other external repos integrate without vendoring.

**Actions:**
- [ ] Define versioned adapter contract spec (schema, CLI boundary, event format)
- [ ] Create `adapters/` directory in ZeusOS repo for external repo integration shims
- [ ] Update `skills/` directory structure to clarify which skills are ZeusOS-native vs external adapters
- [ ] Document adapter contract in `docs/external-repo-integration.md`
- [ ] Ensure `plugins/hermes_zeus_gateway/` uses adapter contract, not direct repo access

---

## 4. Backward Compatibility Strategy

### 4.1 Package / Import Paths

| Before | After | Compatibility |
|--------|-------|---------------|
| `import jinwang_jarvis` | `import zeus_os` | Phase 1-3: both work via shim |
| `from jinwang_jarvis.cli import main` | `from zeus_os.cli import main` | Phase 1-3: both work via shim |
| `python -m jinwang_jarvis.cli` | `python -m zeus_os.cli` | Phase 1: `zeus-os` CLI alias added; Phase 3: primary name |

**Shim strategy:**
```python
# src/jinwang_jarvis/__init__.py (Phase 3+)
"""Backward-compatibility shim for jinwang-jarvis."""
import sys
from zeus_os import *
# Re-export everything
```

### 4.2 CLI Commands

| Current | Phase 1 | Phase 3 |
|---------|---------|---------|
| `jinwang-jarvis collect-mail` | `jinwang-jarvis collect-mail` (primary) + `zeus-os collect-mail` (alias) | `zeos-os collect-mail` (primary) + `jinwang-jarvis` (alias) |
| `jinwang-jarvis zeus task submit` | unchanged | `zeus-os zeus task submit` |
| `jinwang-jarvis hooo start` | unchanged | `zeus-os hooo start` |

### 4.3 Plugins

| Current Plugin | Phase 1 | Phase 3 |
|----------------|---------|---------|
| `hermes_hooo_gateway` | unchanged | unchanged |
| `hermes_zeus_gateway` | unchanged | unchanged |
| `hermes_jarvis_styled_voice_gateway` | unchanged | rename to `hermes_zeusos_styled_voice_gateway` |

**Hermes plugin loading:** Hermes discovers plugins via symlink from `~/.hermes/plugins/`. Renaming the source directory requires re-symlinking. Phase 3 must include a migration script.

### 4.4 systemd / Cron

| Current Unit | Phase 1 | Phase 3 |
|--------------|---------|---------|
| `jinwang-jarvis-cycle.service` | add `zeusos-cycle.service` as symlink/alias | `zeusos-cycle.service` becomes primary; old unit disabled |
| `jinwang-jarvis-weekly-review.service` | add alias | `zeusos-weekly-review.service` primary |
| `jinwang-jarvis-hermes-health.service` | add alias | `zeusos-hermes-health.service` primary |
| `hermes-gateway.service` | **never rename** (Hermes boundary) | **never rename** |

**Cron jobs:** Hermes cron runs inside `hermes-gateway.service`. The `jobs.json` format references command paths. Phase 1-2: keep `jinwang_jarvis` module paths. Phase 3: update cron jobs to use `zeus_os` paths, with Hermes restart.

### 4.5 Wiki

| Artifact | Current | Phase 2 | Phase 3 |
|----------|---------|---------|---------|
| Entity page | `entities/jinwang-jarvis.md` | create `entities/zeusos.md`; update jarvis page with legacy note | `entities/zeusos.md` canonical |
| Concept page | none | create `concepts/zeusos-as-hermes-enhancement-layer.md` | maintained |
| Generated notes | `queries/jinwang-jarvis-*` | add `queries/zeusos-*` paths; keep old for 30 days | migrate fully |
| Wiki search index | indexes both | update FTS sidecar tables | `zeusos` as owner/generator |

### 4.6 Skills

| Skill | Current | Phase 3 |
|-------|---------|---------|
| `discord-voice-stt-enhance` | unchanged | unchanged |
| `hooo` | unchanged | update SKILL.md to reference ZeusOS |
| `houroboros` | unchanged | update SKILL.md to reference ZeusOS |
| `styled-voice` | unchanged | update SKILL.md to reference ZeusOS |

---

## 5. Source-Untouched Hermes Boundary

**Invariant:** No commit in ZeusOS may modify files under `~/.hermes/hermes-agent/` or the Hermes source repository.

**Current Integration Points (all safe):**

1. **Plugins:** `plugins/hermes_*_gateway/` — loaded by Hermes via symlink from `~/.hermes/plugins/`
2. **systemd:** `systemd/hermes-gateway.service` — rendered by ZeusOS, installed by user to `~/.config/systemd/user/`
3. **Health checks:** `jinwang-jarvis-hermes-health.service` — calls Hermes APIs passively
4. **Skill lifecycle:** `hermes_skill_lifecycle.py`, `hermes_skill_search.py` — read-only scans of `~/.hermes/skills/`
5. **Telemetry:** `state/hermes-skill-usage.json` — ZeusOS-owned sidecar, never writes to Hermes

**Migration Impact on Hermes:**
- Phase 1-2: **Zero impact.** Only aliases added in ZeusOS.
- Phase 3: **Minimal impact.** Requires:
  - Re-symlinking plugins if plugin directories are renamed
  - Updating Hermes `config.yaml` `skills.external_dirs` if paths change
  - Restarting `hermes-gateway.service` to pick up new cron job paths

**Hermes config changes (Phase 3):**
```yaml
# ~/.hermes/config.yaml changes
skills:
  external_dirs:
    - /home/jinwang/workspace/jinwang-jarvis/skills  # or /home/jinwang/workspace/zeus-os/skills after repo rename
```

---

## 6. External Repo Adapter / Capability Contract Stance

**Principle:** K-Skill and other external repositories remain independent source-of-truth. ZeusOS integrates them through versioned adapter contracts, CLI boundaries, and artifact/event projections — never by vendoring.

**Current State:**
- `skills.external_dirs` in Hermes config already points to `/home/jinwang/workspace/jinwang-jarvis/skills/`
- This is effectively a file-system-level adapter, not a code dependency
- The `discord-voice-stt-enhance` skill has its own runtime, tests, and service files

**Recommended Adapter Contract (Phase 4):**

```yaml
# adapters/k-skill/contract.yaml (new)
adapter_version: "1.0.0"
upstream_repo: "github.com/.../k-skill"
integration_type: "skill_bundle"  # or "cli_command", "event_stream", "artifact_projection"
interface:
  skills_dir: "skills/k-skill/"
  cli_commands: []
  events: []
  artifacts: []
version_constraint: ">=2.0.0"
```

**Implementation:**
- ZeusOS `adapters/` directory contains only lightweight shims and contract definitions
- Heavy logic stays in external repos
- Version pinning via git tags or submodules (if needed), but prefer loose coupling via CLI contracts

---

## 7. Risk Register and Gates

| Risk | Likelihood | Impact | Mitigation | Gate |
|------|-----------|--------|------------|------|
| **Breaking systemd timers** | Medium | High | Keep old units disabled; test in non-production environment first | Gate 1: All timers verified in staging VM before production |
| **Hermes plugin path breakage** | Medium | High | Do not rename plugins until Phase 3; test Hermes restart | Gate 2: Hermes gateway restart test passes with all plugins loaded |
| **Import path breakage in tests** | Low | Medium | Maintain `jinwang_jarvis` shim throughout Phase 3 | Gate 3: `pytest -q` passes before and after rename |
| **GitHub redirect expiry** | Low | Medium | GitHub redirects are durable; update local remotes immediately | Gate 4: Clone from new URL works; old URL redirects |
| **Wiki/generated note path breakage** | Medium | Medium | Keep old paths for 30 days; use symlinks | Gate 5: Wiki semantic lint passes with zero generated/canonical boundary errors |
| **Discord command name confusion** | Medium | Low | Discord commands are Hermes-side; ZeusOS only affects delivery channel config | Gate 6: Discord delivery test passes after rename |
| **Data file path mismatch** | Low | High | Database paths are configurable in `pipeline.local.yaml`; keep defaults stable | Gate 7: Full pipeline cycle runs end-to-end after rename |
| **External repo skill path breakage** | Medium | Medium | `skills.external_dirs` must be updated in Hermes config after repo rename | Gate 8: All skills load correctly in Hermes after path update |

### Gate Checklist (must pass before each phase advances)

**Pre-Phase 1:**
- [ ] Jinwang approves this plan
- [ ] Backup of `state/` and `data/` directories

**Pre-Phase 2:**
- [ ] Phase 1 PR merged and deployed for 48h without issues
- [ ] All CLI aliases tested manually

**Pre-Phase 3:**
- [ ] Phase 2 docs updated and reviewed
- [ ] All gates 1-8 pass in staging environment
- [ ] Rollback script tested (repo rename reversal, unit restore)

**Pre-Phase 4:**
- [ ] Phase 3 stable for 1 week
- [ ] Adapter contract spec reviewed by Jinwang

---

## 8. Concrete First PR Scope

**PR Title:** `feat: Add ZeusOS CLI aliases and compatibility shims (Phase 1)`

**Files to modify:**

| File | Change |
|------|--------|
| `pyproject.toml` | Add `zeus-os` console_scripts entry point; add package metadata alias |
| `src/jinwang_jarvis/cli.py` | Add `zeus-os` prog fallback; add `zeus` alias detection |
| `src/jinwang_jarvis/runtime.py` | Add `zeusos-*` service name variants alongside `jinwang-jarvis-*` |
| `scripts/install.sh` | Add `--product-name` flag; default `jinwang-jarvis` |
| `systemd/` | Add `zeusos-cycle.service`, `zeusos-weekly-review.service`, `zeusos-hermes-health.service` as copies/aliases |
| `README.md` | Add dual-branding header; update quick-start to show both CLIs |
| `src/zeus_os/__init__.py` | New file: re-export shim from `jinwang_jarvis` (Phase 1 placeholder) |
| `tests/test_cli.py` | Add tests for `zeus-os` CLI alias |

**Files NOT to modify in Phase 1:**
- `src/jinwang_jarvis/` directory structure
- Any test imports
- Any production systemd unit names (only add new ones)
- GitHub repo name
- Hermes config or plugins

**Test plan:**
1. `pip install -e .` — both `jinwang-jarvis` and `zeus-os` CLI entry points exist
2. `zeus-os --help` shows same help as `jinwang-jarvis --help`
3. `zeus-os collect-mail --config config/pipeline.local.yaml` runs successfully
4. `pytest -q` passes
5. `scripts/install.sh --product-name zeusos --workspace-only` generates `systemd/zeusos-*` units

---

## 9. Open Questions for Jinwang

1. **GitHub repo rename timing:** Do you want to rename the GitHub repository during Phase 3, or keep `jinwang-jarvis` as the repo name indefinitely and only rename the Python package/product? (GitHub redirects are reliable but some tools may cache old URLs.)

2. **Database file names:** Should `state/jarvis.sqlite3` and `state/jinwang_jarvis.sqlite3` be renamed to `state/zeusos.sqlite3`, or kept as-is since they are data files? (Renaming data files requires migration scripts; keeping them avoids risk.)

3. **Discord bot identity:** The Discord bot is Hermes-side. Should the bot's display name or status message reference "ZeusOS" instead of "Jarvis"? If so, this requires a Hermes config change (not source edit), which is outside ZeusOS scope but should be coordinated.

4. **Hermes `skills.external_dirs` path:** After repo rename, the filesystem path changes from `.../jinwang-jarvis/skills` to `.../zeus-os/skills`. Should Phase 3 include an automated update to `~/.hermes/config.yaml`, or is this a manual step?

5. **Capability pack granularity:** Should "Jarvis" remain as a single capability pack, or should it be split into smaller packs (e.g., `mail-intel`, `calendar-intel`, `hot-issues-radar`) within ZeusOS? This affects module structure but not Phase 1.

6. **K-Skill adapter priority:** Is K-Skill integration urgent enough to include in Phase 4, or should it be deferred to a later roadmap item?

7. **Staging environment:** Do you have a non-production VM or environment where systemd timers and Hermes restart can be safely tested before production deployment?

---

## Appendix A: Complete Rename Impact Inventory

### A.1 Source Code References to "jarvis" / "jinwang-jarvis"

**High-touch files (require rename):**
- `pyproject.toml` — `name = "jinwang-jarvis"`, entry points
- `src/jinwang_jarvis/` — entire package directory
- `src/jinwang_jarvis/cli.py` — `prog="jinwang-jarvis"`, help text
- `src/jinwang_jarvis/runtime.py` — service names, CLI command strings
- `src/jinwang_jarvis/config.py` — `project_name` default
- `src/jinwang_jarvis/wiki_contract.py` — `owner="jarvis"`, `generator="jinwang-jarvis"`
- `src/jinwang_jarvis/intelligence.py` — `INTELLIGENCE_NOTE_DIR`, tags
- `src/jinwang_jarvis/watch.py` — `_jarvis_fetch_status` keys
- `bin/pi_*.py` — `from jinwang_jarvis.cli import main`
- `scripts/install.sh` — `python3 -m jinwang_jarvis.cli`
- `systemd/*.service`, `systemd/*.timer` — unit names, descriptions
- `plugins/hermes_jarvis_styled_voice_gateway/` — directory name, plugin.yaml

**Medium-touch files (help text, descriptions):**
- `src/jinwang_jarvis/cli.py` — ~30 help strings referencing "Jarvis"
- `src/jinwang_jarvis/hermes_continuity.py` — "Jarvis-hosted styled-voice skill"
- `src/jinwang_jarvis/hermes_skill_search.py` — "Jarvis-owned Hermes skill retrieval"
- `README.md` — product name, examples
- `docs/*.md` — all documentation

**Low-touch files (comments, internal naming):**
- `tests/test_*.py` — test descriptions, config fixtures
- `docs/cron.md` — command examples
- `config/pipeline.yaml` — `project_name: jinwang-jarvis`

### A.2 Hermes Integration Points

| Point | File | Phase 3 Action |
|-------|------|----------------|
| Plugin: HOOO gateway | `plugins/hermes_hooo_gateway/` | No rename needed |
| Plugin: Zeus gateway | `plugins/hermes_zeus_gateway/` | No rename needed |
| Plugin: Styled voice | `plugins/hermes_jarvis_styled_voice_gateway/` | Rename to `hermes_zeusos_styled_voice_gateway` |
| systemd: Gateway service | `systemd/hermes-gateway.service` | **Never rename** |
| Health check service | `systemd/jinwang-jarvis-hermes-health.*` | Rename to `zeusos-hermes-health.*` |
| Recovery script | `scripts/arm-opencode-gateway-recovery.sh` | No rename needed |

### A.3 State / Data Files

| File | Identity-bearing? | Recommended Action |
|------|-------------------|-------------------|
| `state/jarvis.sqlite3` | Yes | Rename or symlink to `state/zeusos.sqlite3` in Phase 3 |
| `state/jinwang_jarvis.sqlite3` | Yes | Rename or symlink |
| `state/personal_intel.db` | No | Keep as-is (data file) |
| `state/houroboros.db` | No | Keep as-is |
| `state/hermes-skill-usage.json` | No | Keep as-is |
| `state/external_hot_issue_state.json` | No | Keep as-is |
| `data/jarvis.sqlite` | Yes | Rename or symlink |

---

## Appendix B: Rollback Procedures

### B.1 GitHub Repo Rename Rollback
```bash
# If rename was a mistake, GitHub allows reverting within a short window
# Otherwise, create a new repo with old name and push a mirror
git clone --mirror https://github.com/JinwangMok/zeus-os.git
cd zeus-os.git
git remote set-url origin https://github.com/JinwangMok/jinwang-jarvis.git
git push --mirror
```

### B.2 systemd Unit Rollback
```bash
systemctl --user disable zeusos-cycle.timer zeusos-hermes-health.timer
systemctl --user enable jinwang-jarvis-cycle.timer jinwang-jarvis-hermes-health.timer
systemctl --user daemon-reload
```

### B.3 Python Package Rollback
```bash
pip uninstall zeus-os
pip install -e .  # from jinwang-jarvis branch
```

### B.4 Database Path Rollback
```bash
cd /home/jinwang/workspace/jinwang-jarvis
ln -sf zeusos.sqlite3 jarvis.sqlite3  # or reverse symlink
```

---

*End of migration plan. This document was produced by external contractor lane #1 as a read-only analysis artifact. No production source files were modified during its creation.*
