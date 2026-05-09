# Repo Rename Impact Audit: jinwang-jarvis → ZeusOS

**Date:** 2026-05-06
**Lane:** #2 (External Contractor)
**Scope:** Read-only impact mapping. No production source files modified.
**Controller Comparison Target:** Hermes MoA + Lane #1 artifact

---

## Executive Summary

A full rename of `jinwang-jarvis` to `ZeusOS` touches **≥130 files** across **11 distinct categories** of breakage risk. The project uses the name at five different conceptual layers:

1. **GitHub org/repo name** (`JinwangMok/jinwang-jarvis`)
2. **PyPI/distribution name** (`jinwang-jarvis` in `pyproject.toml`)
3. **Python import module** (`jinwang_jarvis` in `src/jinwang_jarvis/`)
4. **CLI program name** (`jinwang-jarvis` in `argparse.prog`)
5. **Filesystem/workspace identity** (`jinwang-jarvis` in paths, systemd units, wiki nodes, DB files, generator metadata)

The safest migration path is a **phased compatibility strategy**: keep the Python module name alive via namespace aliases, rename the distribution/PyPI name, introduce `zeus` CLI aliases alongside existing commands, and defer filesystem-level renames until a coordinated cutover window.

---

## 1. Rename Surface Inventory Table

| # | Path / Pattern | Current Name | Proposed Handling | Risk Level |
|---|----------------|--------------|-------------------|------------|
| 1 | `pyproject.toml:project.name` | `jinwang-jarvis` | Rename to `zeusos` or `zeus-os`; add `jinwang-jarvis` as PyPI alias/redirect | **Medium** |
| 2 | `src/jinwang_jarvis/` (package dir) | `jinwang_jarvis` | Keep as compatibility shim; create `zeus_os/` package that re-exports; OR rename with `__init__.py` backward alias | **High** |
| 3 | `src/jinwang_jarvis/__init__.py` imports | `from jinwang_jarvis...` | Keep module name working; new code can use `from zeus_os...` | **High** |
| 4 | `src/jinwang_jarvis/cli.py:prog` | `jinwang-jarvis` | Change to `zeus`; keep `jinwang-jarvis` as deprecated alias | **Medium** |
| 5 | `src/jinwang_jarvis/zeus_os/cli.py:prog` | `jinwang-jarvis zeus` | Change to `zeus` (already planned per docs) | **Low** |
| 6 | `bin/pi_*.py` scripts (9 files) | `from jinwang_jarvis.cli import main` | Update to `zeus_os` OR keep shim | **Low** |
| 7 | `tests/` (49 test files) | `from jinwang_jarvis...` | Bulk update imports; `pytest` will fail until done | **High** |
| 8 | `config/pipeline.yaml:project_name` | `jinwang-jarvis` | Change to `zeusos`; may affect test assertions | **Medium** |
| 9 | `systemd/*.service` / `*.timer` (7 units) | `jinwang-jarvis-*` | Rename to `zeusos-*`; disable old units, enable new; **breaks running timers** | **High** |
| 10 | `src/jinwang_jarvis/runtime.py` constants | `CYCLE_SERVICE_NAME = "jinwang-jarvis-cycle.service"` | Update constants; affects unit generation | **High** |
| 11 | `scripts/install.sh` | Disables `jinwang-jarvis-cycle.timer` etc. | Update to `zeusos-*` names | **Medium** |
| 12 | `docs/` (all 15+ doc files) | `python -m jinwang_jarvis.cli ...` | Update all CLI examples; **user-facing breakage** | **High** |
| 13 | `README.md` | Clone URL `hermes-jarvis`, module path `jinwang_jarvis` | Update clone URL, examples, notes | **High** |
| 14 | `skills/*/SKILL.md` (4 skill dirs) | `python -m jinwang_jarvis.cli ...` | Update CLI examples in skill docs | **Medium** |
| 15 | `plugins/hermes_zeus_gateway/plugin.yaml` | `author: jinwang-jarvis`, requires `jinwang_jarvis >= 0.1.0` | Update to `zeusos` | **Medium** |
| 16 | `plugins/hermes_minerva_gateway/__init__.py` | `JARVIS_ROOT = PLUGIN_ROOT.parents[1]` | Path-relative; safe if repo dir renamed | **Low** |
| 17 | `src/jinwang_jarvis/styled_voice_samples.py` | `~/workspace/jinwang-jarvis/data/styled-voice-samples` | Hardcoded path; **breaks if repo dir renamed** | **High** |
| 18 | `wiki/queries/jinwang-jarvis-*` (live wiki nodes) | `jinwang-jarvis-importance-shift-watchlist.md`, `jinwang-jarvis-memory/` | **Mass wiki link breakage**; rename + redirect needed | **Critical** |
| 19 | `src/jinwang_jarvis/knowledge.py` | `WATCHLIST_NOTE_RELATIVE_PATH = "queries/jinwang-jarvis-importance-shift-watchlist.md"` | Update path constants | **High** |
| 20 | `src/jinwang_jarvis/intelligence.py` | `INTELLIGENCE_NOTE_DIR = "queries/jinwang-jarvis-intelligence"` | Update path constants | **High** |
| 21 | Generator metadata strings | `"generator: jinwang-jarvis"` (appears 25+ times) | Update to `zeusos` or keep for historical fidelity | **Low** |
| 22 | User-Agent headers | `"jinwang-jarvis-news-center/0.2"`, `"jinwang-jarvis-unified-daily-report/0.1"` | Update to `zeusos-*` | **Low** |
| 23 | `state/jinwang_jarvis.sqlite3` | DB filename | Rename or deprecate; code may reference it | **Medium** |
| 24 | `.git/config` remotes | `origin` → `JinwangMok/jinwang-jarvis.git`, `public` → `JinwangMok/hermes-jarvis.git` | Update remotes; GitHub repo rename needed | **Medium** |
| 25 | `scripts/gate_daily_hot_issues_delivery.py` | Banned pattern `jinwang-jarvis/data` | Update gate regex if path conventions change | **Low** |
| 26 | `tests/test_config.py` | Hardcodes `/home/jinwang/workspace/jinwang-jarvis` paths | Must update; currently fails in worktrees already | **High** |
| 27 | `Spec.md` title | `Jinwang Jarvis MVP Execution Spec` | Update title and references | **Low** |
| 28 | `src/jinwang_jarvis/hermes_skill_lifecycle.py` | `"contract": "Hermes agent + jinwang-jarvis"` | Update contract string | **Low** |
| 29 | `src/jinwang_jarvis/hermes_continuity.py` | `"contract": "Hermes agent + jinwang-jarvis"` | Update contract string | **Low** |
| 30 | `orchestration/` artifacts | Many reference `src/jinwang_jarvis/` paths | Historical; do not retroactively edit | **None** |

---

## 2. Breakage Map by Category

### 2.1 Imports (🔴 Critical)
- **Scope:** 49 files in `tests/`, 9 files in `bin/`, 3 files in `plugins/`, 1 file in `skills/`
- **Pattern:** `from jinwang_jarvis.X import Y`, `import jinwang_jarvis`
- **Breakage:** If module directory `src/jinwang_jarvis/` is renamed to `src/zeus_os/` without a compatibility shim, **all imports fail immediately**.
- **Mitigation:** Keep `jinwang_jarvis` as a namespace package or `__init__.py` re-export shim for at least one major version.

### 2.2 CLI Commands (🟠 High)
- **Scope:** `cli.py` (prog=`"jinwang-jarvis"`), all docs, skills, cron examples, systemd ExecStart lines
- **Pattern:** `python -m jinwang_jarvis.cli <command>`
- **Breakage:** All user-facing documentation, scripts, aliases, and systemd units reference the old module path. Changing `prog` also changes help text and error messages.
- **Mitigation:** Add a `jinwang-jarvis` console-scripts entry point that delegates to the new `zeus` CLI. Keep `python -m jinwang_jarvis.cli` working via shim.

### 2.3 Plugin Discovery (🟠 High)
- **Scope:** `plugins/hermes_zeus_gateway/plugin.yaml` (requires `jinwang_jarvis >= 0.1.0`)
- **Pattern:** PyPI package name in plugin requirements
- **Breakage:** Hermes plugin loader checks requirements against installed distribution name. If distribution is renamed, plugin fails to load.
- **Mitigation:** Provide both distribution names (old as alias/redirect), OR update all plugin.yaml files simultaneously.

### 2.4 Test Fixtures (🔴 Critical)
- **Scope:** `tests/test_config.py` (hardcodes `/home/jinwang/workspace/jinwang-jarvis` in 10 assertions)
- **Pattern:** Absolute path assertions; `project_name == "jinwang-jarvis"` assertion
- **Breakage:** Tests fail if workspace path or project_name changes. Already fails in worktrees (observed in `2026-05-02-minerva-team` orchestration artifact).
- **Mitigation:** Make tests path-agnostic or parametrize workspace root; update `project_name` assertion.

### 2.5 Cron Jobs / Systemd Units (🔴 Critical)
- **Scope:** 7 unit files in `systemd/`, `scripts/install.sh`, `src/jinwang_jarvis/runtime.py` unit generators
- **Files:**
  - `jinwang-jarvis-cycle.service`
  - `jinwang-jarvis-cycle.timer`
  - `jinwang-jarvis-weekly-review.service`
  - `jinwang-jarvis-weekly-review.timer`
  - `jinwang-jarvis-hermes-health.service`
  - `jinwang-jarvis-hermes-health.timer`
  - `hermes-gateway.service` (references workspace path)
- **Breakage:** Unit names are hardcoded in Python constants (`runtime.py`), shell scripts (`install.sh`), and live systemd user state. Changing names without disabling old units first creates ghost timers.
- **Mitigation:**
  1. `install.sh` must disable old units before enabling new ones
  2. `runtime.py` constants must be updated
  3. User must run `systemctl --user daemon-reload`

### 2.6 Wiki Links (🔴 Critical)
- **Scope:** `wiki/queries/jinwang-jarvis-*`, `wiki/queries/jinwang-jarvis-memory/`, `wiki/queries/jinwang-jarvis-intelligence/`
- **Pattern:** Wiki node filenames and internal `[[...]]` links
- **Breakage:** `knowledge.py`, `intelligence.py`, `wiki_contract.py` hardcode relative paths like `queries/jinwang-jarvis-importance-shift-watchlist.md`. Renaming breaks:
  - Wiki graph links
  - Generated memory note paths
  - Watchlist index entries
  - Intelligence report directory structure
- **Mitigation:** Batch-rename wiki files + update all path constants in source. Consider wiki symlink redirects for compatibility.

### 2.7 Skills (🟠 High)
- **Scope:** `skills/minerva/SKILL.md`, `skills/minerva/SKILL.md`, `skills/styled-voice/SKILL.md`
- **Pattern:** CLI examples reference `python -m jinwang_jarvis.cli ...`
- **Breakage:** Skill documentation becomes incorrect. Hermes skill search indexes may reference old names.
- **Mitigation:** Update SKILL.md files. No runtime breakage if CLI shim is kept.

### 2.8 Docs (🟠 High)
- **Scope:** All 15+ `.md` files in `docs/`, `README.md`, `Spec.md`
- **Pattern:** Clone URLs, CLI examples, config references
- **Breakage:** User-facing documentation becomes misleading. `README.md` already notes "The Python module path is still `jinwang_jarvis` for compatibility" — indicating this is a known tension.
- **Mitigation:** Bulk update all docs. Keep a "Migration from jinwang-jarvis" section.

### 2.9 Artifact Paths (🟡 Medium)
- **Scope:** `data/`, `state/` directories (live runtime artifacts)
- **Pattern:** `state/jinwang_jarvis.sqlite3` exists; `data/` subdirs use generic names
- **Breakage:** Most artifact paths are generic (`data/snapshots/mail`, `state/personal_intel.db`). Only `state/jinwang_jarvis.sqlite3` and `data/jarvis.sqlite` use the old name.
- **Mitigation:** Rename or deprecate old DB files. `bootstrap.py` creates `personal_intel.db` as the canonical DB now.

### 2.10 Database / Workspace Paths (🟠 High)
- **Scope:** `config/pipeline.yaml`, `styled_voice_samples.py`, test fixtures
- **Pattern:** `~/workspace/jinwang-jarvis/data/styled-voice-samples`, hardcoded `/home/jinwang/workspace/jinwang-jarvis`
- **Breakage:** If the repo directory is physically renamed on disk, `styled_voice_samples.py` default path breaks. Tests break.
- **Mitigation:** Make `styled_voice_samples.py` path relative to workspace_root config instead of hardcoded home path.

### 2.11 External Adapters (🟡 Medium)
- **Scope:** GitHub `public` remote (`hermes-jarvis`), Discord bot integrations, Hermes gateway
- **Pattern:** Public repo name differs from private repo name already (`hermes-jarvis` vs `jinwang-jarvis`)
- **Breakage:** GitHub public remote rename affects clone URLs. Discord/webhook integrations that reference repo URLs may break.
- **Mitigation:** GitHub provides automatic redirects for renamed repos. Update public remote after rename.

---

## 3. Recommended Compatibility Matrix

| Surface | Strategy | Rationale | Effort |
|---------|----------|-----------|--------|
| **PyPI/distribution name** | **Rename** to `zeusos`; publish `jinwang-jarvis` as final maintenance release with deprecation warning | Clean branding; PyPI name is user-facing | Medium |
| **Python module name (`jinwang_jarvis`)** | **Keep** as compatibility shim via `src/jinwang_jarvis/__init__.py` re-exporting from `zeus_os` | Prevents import breakage across plugins, tests, skills | Low (if done early) |
| **CLI `python -m jinwang_jarvis.cli`** | **Alias** — keep working but emit deprecation warning; primary path becomes `python -m zeus_os.cli` or just `zeus` | User scripts and systemd units depend on this | Low |
| **Systemd unit names** | **Rename** to `zeusos-*`; `install.sh` disables old units before enabling new | Old names are branded; can't alias systemd units | High |
| **Wiki node paths** | **Rename** files from `jinwang-jarvis-*` to `zeusos-*`; update all source constants; consider 1-week transition with symlinks | Wiki is a living knowledge graph; stale links rot | High |
| **Generator metadata** | **Rename** to `zeusos` going forward; historical artifacts can keep old name | Low risk; mostly cosmetic | Low |
| **User-Agent headers** | **Rename** to `zeusos-*` | External services may log/filter on UA | Low |
| **GitHub repo name** | **Rename** `JinwangMok/jinwang-jarvis` → `JinwangMok/zeusos`; GitHub redirects old URLs automatically | Canonical project identity | Low |
| **Config `project_name`** | **Rename** to `zeusos`; update test assertions | Aligns with new branding | Low |
| **Test hardcoded paths** | **Fix** to be workspace-agnostic (use `tmp_path`, `Path.cwd()`, or config-driven) | Already broken in worktrees; should be fixed regardless | Medium |
| **Skills docs** | **Update** SKILL.md CLI examples | Documentation only | Low |
| **Orchestration artifacts** | **No-touch** (historical) | Past work trees are immutable records | None |
| **Live DB files** | **Keep** old names or migrate on first run; don't rename active DBs under running processes | Risk of corrupting live SQLite | Low |

---

## 4. Search Commands / Run Evidence Summary

### 4.1 Grep Evidence
```bash
# Total "jinwang" matches across repo (excluding .git, .venv)
grep -r "jinwang" --include="*" /home/jinwang/workspace/jinwang-jarvis \
  | grep -v ".git/" | grep -v ".venv/" | wc -l
# Result: 723 matches in 130 files

# Python import references
grep -rl "from jinwang_jarvis\|import jinwang_jarvis" /home/jinwang/workspace/jinwang-jarvis \
  | grep -v ".git" | grep -v ".venv"
# Result: 49 files

# "jinwang_jarvis" or "jinwang-jarvis" in src/ only
grep -rc "jinwang_jarvis\|jinwang-jarvis" /home/jinwang/workspace/jinwang-jarvis/src/jinwang_jarvis/*.py
# Result: 61 matches across 13 source files

# "hermes-jarvis" references (public repo name)
grep -rl "hermes-jarvis" /home/jinwang/workspace/jinwang-jarvis \
  | grep -v ".git" | grep -v ".venv"
# Result: 6 files (README, docs, skills, plugins)
```

### 4.2 File Inventory Evidence
```bash
# Python package structure
ls /home/jinwang/workspace/jinwang-jarvis/src/jinwang_jarvis/
# 42 Python modules + __init__.py

# Systemd units
ls /home/jinwang/workspace/jinwang-jarvis/systemd/
# 7 unit files (all prefixed jinwang-jarvis- except hermes-gateway.service)

# Plugin configs
ls /home/jinwang/workspace/jinwang-jarvis/plugins/
# 3 plugins: hermes_minerva_gateway, hermes_jarvis_styled_voice_gateway, hermes_zeus_gateway

# Live DB files in state/
ls /home/jinwang/workspace/jinwang-jarvis/state/
# personal_intel.db (canonical), jinwang_jarvis.sqlite3 (legacy), jarvis.sqlite (legacy)

# Wiki query nodes
ls /home/jinwang/workspace/jinwang-jarvis/wiki/queries/
# jinwang-jarvis-importance-shift-watchlist.md, jinwang-jarvis-intelligence/, jinwang-jarvis-mail-patterns-and-monthly-events-36m.md
```

### 4.3 Git Remote Evidence
```bash
git remote -v
# origin  https://github.com/JinwangMok/jinwang-jarvis.git (fetch/push)
# public  https://github.com/JinwangMok/hermes-jarvis.git (fetch/push)
```

### 4.4 Key Source File References
| File | Lines | Key Findings |
|------|-------|-------------|
| `pyproject.toml` | 6 | `name = "jinwang-jarvis"` |
| `config/pipeline.yaml` | 29 | `project_name: jinwang-jarvis` |
| `src/jinwang_jarvis/cli.py` | 40 | `prog="jinwang-jarvis"` |
| `src/jinwang_jarvis/zeus_os/cli.py` | 15 | `prog="jinwang-jarvis zeus"` |
| `src/jinwang_jarvis/runtime.py` | 29-35 | Hardcoded service name constants |
| `src/jinwang_jarvis/bootstrap.py` | 8-20 | `REQUIRED_DIRECTORIES` (generic paths) |
| `src/jinwang_jarvis/styled_voice_samples.py` | 11-14 | Hardcoded `~/workspace/jinwang-jarvis/...` |
| `src/jinwang_jarvis/knowledge.py` | 13-16 | Hardcoded wiki relative paths |
| `src/jinwang_jarvis/intelligence.py` | 78 | `INTELLIGENCE_NOTE_DIR = "queries/jinwang-jarvis-intelligence"` |
| `tests/test_config.py` | 11-24 | 10 hardcoded absolute path assertions |

---

## 5. Minimal Safe Diff Proposal for First PR

**Goal:** Introduce ZeusOS branding without breaking any running systems.

### PR 1: "Introduce ZeusOS aliases and branding"
**Scope:** Additive changes only. No deletions. No renames.

1. **`pyproject.toml`**
   - Add `[project.scripts]` entry: `zeus = "zeus_os.cli:main"` (or keep via `jinwang_jarvis` shim)
   - Keep `name = "jinwang-jarvis"` unchanged for now

2. **`src/jinwang_jarvis/cli.py`**
   - Add `zeus` as an alias command or subparser that delegates to existing logic
   - Keep `prog="jinwang-jarvis"` unchanged

3. **`src/jinwang_jarvis/zeus_os/cli.py`**
   - Change `prog="jinwang-jarvis zeus"` → `prog="zeus"` (this is Zeus-specific CLI)

4. **`README.md`**
   - Add a prominent "Also available as ZeusOS" banner
   - Keep existing examples; add `zeus` equivalents alongside

5. **`docs/zeus-os-*.md`**
   - Already use `python -m jinwang_jarvis.cli zeus ...`; no change needed

**Explicitly OUT of scope for PR 1:**
- Renaming `src/jinwang_jarvis/` directory
- Changing systemd unit names
- Renaming wiki files
- Updating test hardcoded paths
- Changing PyPI name
- Removing `jinwang-jarvis` CLI

### PR 2: "Add backward-compatible module shim"
**Scope:** Enable `from zeus_os import X` alongside `from jinwang_jarvis import X`.

1. Create `src/zeus_os/` package that re-exports from `jinwang_jarvis`
2. OR: rename directory and create `src/jinwang_jarvis/__init__.py` shim
3. Update `pyproject.toml` package discovery to include both

### PR 3: "Rename systemd units and update install script"
**Scope:** Operator-facing infrastructure rename.

1. Update `runtime.py` constants
2. Rename `systemd/*.service` and `*.timer` files
3. Update `scripts/install.sh` to disable old / enable new
4. Update `docs/cron.md`, `docs/playbooks.md`

### PR 4: "Migrate wiki paths and generator metadata"
**Scope:** Content-level rename. Requires wiki downtime or atomic batch operation.

1. Rename wiki files
2. Update `knowledge.py`, `intelligence.py`, `wiki_contract.py` path constants
3. Update generator strings
4. Update User-Agent headers

### PR 5: "Finalize distribution rename"
**Scope:** Last step. Only after all shims are proven stable.

1. Rename `pyproject.toml` `project.name` to `zeusos`
2. Publish `jinwang-jarvis` as final maintenance release with migration note
3. Update `plugins/*/plugin.yaml` requirements
4. Update GitHub repo name (GitHub auto-redirects)

---

## 6. Explicit No-Touch List

The following must **NOT** be modified, renamed, or deleted under any circumstances during the rename process:

1. **`/home/jinwang/.hermes/` directory and all subpaths** — Hermes source-untouched contract. No modifications to Hermes agent, config, skills, or gateway.
2. **Live SQLite databases under `state/`** — `personal_intel.db`, `minerva.db`, `zeus_os.db` (if exists). Do not rename or move while processes may hold connections.
3. **Historical `orchestration/` artifacts** — Past worktree results, QA evidence, and controller logs are immutable records. Do not retroactively edit.
4. **Raw wiki content outside of `queries/jinwang-jarvis-*` paths** — Operator's personal wiki notes (`reports/`, other `queries/`) are user data.
5. **`data/` artifact subdirectories with generic names** — `data/snapshots/`, `data/proposals/`, `data/briefings/`, etc. already use neutral names; do not rename.
6. **`config/pipeline.local.yaml`** — Operator's private config with credentials and personal paths.
7. **`.git/` repository internals** — No manual editing of git objects, reflog, or packed-refs.
8. **GitHub `public` remote (`hermes-jarvis`)** — The public-facing repo name should be changed only after the private repo rename is complete and verified, to avoid broken public clone URLs.
9. **`skills/` external skill repos** — `skills/discord-voice-stt-enhance/` and any skill submodules are independent repositories; do not touch.
10. **`tests/` should not be deleted or skipped** — Failing tests must be fixed, not removed. The `test_config.py` worktree path issue is pre-existing and should be fixed properly.

---

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import breakage across plugins | High | High | Keep `jinwang_jarvis` module shim |
| Systemd timer ghosts (old + new running) | Medium | High | `install.sh` must disable old before enabling new |
| Wiki link rot | High | High | Batch rename + symlink redirects |
| Test suite fails after rename | High | Medium | Fix test_config.py path assumptions first |
| Plugin loader rejects new distribution name | Medium | High | Publish both names to PyPI temporarily |
| User scripts break | Medium | High | Keep CLI aliases for 1+ release cycles |
| Discord/webhook integrations break | Low | Medium | GitHub auto-redirects handles repo URL |
| Hermes gateway restart triggered | Low | Critical | Explicit no-touch on Hermes files |

---

*Audit completed by Lane #2. No production source files were modified. All findings are based on read-only inspection of the repository at commit `HEAD` on 2026-05-06.*
