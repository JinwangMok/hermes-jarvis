# ZeusOS End-to-End Replay / Gap Audit & Gated Execution Plan

**Date:** 2026-05-07
**Auditor:** Kimi (Sisyphus)
**Scope:** Read-only replay of the current Discord session, gap analysis against AS-IS -> TO-BE diagrams/checklists, and gated substage execution plan.
**Constraint:** No production source edits. Hermes untouched. No gateway/systemd restart.
**Commits on record:** `05d7b12` (browser recipe stance), `1a70959` (compatibility migration contract).

---

## 1. Conversation Replay: Decisions Made So Far

### 1.1 2026-05-05 — Zeus OS Foundation Implementation
- **Decision:** Implement a deterministic, stdlib-only Agent OS control plane under `src/jinwang_jarvis/zeus_os/`.
- **Delivered:** 13 source modules (`schema`, `store`, `queue`, `events`, `artifacts`, `safety`, `doctor`, `boardroom`, `a2a`, `painter`, `export`, `ids`, `cli`), 72 tests (all passing), 2 docs, 1 Hermes plugin (`hermes_zeus_gateway`).
- **Integration point:** `src/jinwang_jarvis/cli.py` gained a `zeus` top-level subparser delegating to `handle_zeus()`.
- **Invariants established:** SQLite + filesystem artifacts are canonical; Discord/markdown are projections; Hermes source untouched.

### 1.2 2026-05-06 — External Contractor Lanes #1 and #2
- **Lane #1 (Migration Plan):** Proposed a 4-phase migration (Phase 0 foundation, Phase 1 aliases, Phase 2 docs/wiki, Phase 3 production rename, Phase 4 adapter contracts). Recommended `zeus-os` CLI aliases, `src/zeus_os/` shim, and `zeusos-*` systemd variants in PR #1.
- **Lane #2 (Impact Audit):** Inventory of >=130 files across 11 breakage categories. Identified hardcoded paths in `tests/test_config.py`, `styled_voice_samples.py`, `knowledge.py`, `intelligence.py`; systemd unit constants in `runtime.py`; wiki path constants; 723 total "jinwang" matches.

### 1.3 2026-05-06 — Converged Controller Verdict (Boramae/Hermes)
- **Decision:** Proceed **only** as a compatibility-first product/architecture migration. **Reject** big-bang rename.
- **Key convergence:**
  - Hermes remains source-untouched.
  - External repos remain independent via adapter contracts.
  - `src/jinwang_jarvis/`, `python -m jinwang_jarvis.cli`, systemd units, wiki paths are **high-blast-radius** and must not change in PR #1.
  - PR #1 scope = docs/metadata/contract-first only.
- **Disagreement resolved:** Lane #1 was too aggressive; MoA + Lane #2 converged on a safer docs-first PR.
- **Required gates before any code rename:** identity matrix, import/CLI test plan, active automation inventory, wiki rename plan, data backup/rollback, Hermes no-touch verification.

### 1.4 2026-05-07 — Documentation Commits
- **`1a70959`:** `docs/zeus-os-rebrand-migration.md` — compatibility-first contract, identity taxonomy, non-negotiable invariants, rename surface matrix, phased roadmap (Phase 0-4), gates checklist.
- **`05d7b12`:** `docs/zeus-os-adapter-contract.md` — external adapter boundaries, manifest shape, approval mapping, artifact contract, portable browser recipe provenance rules.
- **`README.md`:** Updated with ZeusOS product identity, Jarvis capability-pack status, compatibility surface definitions.

### 1.5 Taxonomy Frozen by Contract
| Name | Meaning | Handling |
|---|---|---|
| **ZeusOS** | Product/control-plane and Agent OS identity | Forward-facing |
| **Jarvis** | Personal-intelligence capability pack (mail, calendar, briefing, radar, Minerva) | Retained; not erased |
| **`jinwang-jarvis`** | Repo/distribution/local workspace identity | Compatibility surface; do not rename yet |
| **`jinwang_jarvis`** | Python import namespace | Compatibility surface; keep canonical until aliases proven |
| **Hermes** | Gateway/runtime/tool host | Source-untouched; integrate via plugins/configs/CLI |
| **External repos (K-Skill, etc.)** | Independent capability providers | Adapter contracts; not vendored |
| **Portable browser recipes** | Reusable harness helpers, selectors, SKILL.md playbooks | Provenanced artifacts; not live helper mutation |

---

## 2. Missing Items from the AS-IS -> TO-BE Diagram / Checklist

### 2.1 Critical Missing Artifacts

The committed docs and contractor lanes provide **narrative plans** and **impact inventories**, but they do **not** constitute a formal, machine-verifiable AS-IS -> TO-BE transition artifact. The following are missing:

#### A. Formal AS-IS Architecture Diagram
- **Status:** Missing.
- **What exists:** A boundary map in Lane #1 (Section 2.2) and the identity taxonomy table.
- **Gap:** No visual or structured diagram showing the **current runtime topology** with actual file paths, DB names, systemd unit names, Hermes plugin symlinks, cron jobs, and active config paths.
- **Impact:** Cannot verify that every surface has been classified.

#### B. Formal TO-BE Architecture Diagram
- **Status:** Missing.
- **What exists:** Boundary map in Lane #1 showing target structure abstractly.
- **Gap:** No diagram showing the **target state** after all phases complete, including which surfaces remain `jinwang-jarvis` permanently, which get aliases, which get renamed, and the Hermes profile split topology.

#### C. Identity Matrix (Rename Surface Checklist)
- **Status:** Partial — rename surface matrix exists in `docs/zeus-os-rebrand-migration.md` (Section: "Rename surface matrix").
- **Gap:** The matrix only covers **first-step decision** (keep/rename-later). It does **not** cover:
  - Every import statement in tests/bin/plugins (49+ files)
  - Every generator metadata string (25+ occurrences)
  - Every User-Agent header
  - Every wiki node path beyond `queries/jinwang-jarvis-*`
  - Every `SKILL.md` reference to `python -m jinwang_jarvis.cli`
  - Every hardcoded path in `tests/test_config.py`
- **Impact:** Cannot claim 100% surface coverage.

#### D. Import / CLI Compatibility Test Plan
- **Status:** Mentioned as Gate 2 in migration doc, but **not specced**.
- **Gap:** No explicit test fixtures or test cases proving that both `from jinwang_jarvis...` and `from zeus_os...` work simultaneously. No regression test for CLI parser drift.
- **Impact:** Cannot prove aliases are safe before deployment.

#### E. Active Automation Inventory
- **Status:** Mentioned as Gate 3 / Gate 5 in migration doc, but **not produced**.
- **Gap:** No document listing:
  - `systemctl --user list-timers` output
  - Hermes cron job entries
  - Plugin symlinks in `~/.hermes/plugins/`
  - Active config paths (`config/pipeline.local.yaml`, `~/.hermes/config.yaml`)
  - Discord bot integration points
- **Impact:** Cannot assess blast radius of any rename.

#### F. Wiki Migration Plan with Exact Path Mappings
- **Status:** Mentioned in Lane #2 and migration doc, but **not specced with exact paths**.
- **Gap:** No table mapping each `queries/jinwang-jarvis-*` path to its target `queries/zeusos-*` path. No plan for `raw/` protection. No redirect/symlink strategy.
- **Impact:** Wiki link rot risk remains unquantified.

#### G. Data Backup / Rollback Procedures
- **Status:** Mentioned as Gate 6 in migration doc, but **not documented**.
- **Gap:** No explicit backup commands for `state/` and `data/`. No rollback script. No verification that `personal_intel.db`, `minerva.db`, `zeus_os.db` can be restored.
- **Impact:** Cannot safely proceed to any phase that touches live data.

#### H. Zeus CLI Parser Drift Fix Plan
- **Status:** Identified as a blocker in converged verdict and migration doc.
- **Gap:** `src/jinwang_jarvis/cli.py` has a `build_zeus_parser()` function (lines 331-428) that is a **near-duplicate** of `src/jinwang_jarvis/zeus_os/cli.py:build_zeus_parser()` (lines 14-114). The converged verdict says to "deduplicate or add regression tests covering both." **Neither a deduplication plan nor regression tests exist yet.**
- **Impact:** Any change to Zeus CLI must be made in two places, guaranteeing drift.

#### I. Path-Hardcoding Audit Remediation Plan
- **Status:** Identified in Lane #2 and migration doc.
- **Gap:** No explicit task list for fixing each hardcoded path:
  - `tests/test_config.py` — 10 assertions with `/home/jinwang/workspace/jinwang-jarvis`
  - `styled_voice_samples.py` — `~/workspace/jinwang-jarvis/data/styled-voice-samples`
  - `knowledge.py` — `queries/jinwang-jarvis-*` paths
  - `intelligence.py` — `queries/jinwang-jarvis-intelligence` path
  - `wiki_contract.py` — generator metadata strings
- **Impact:** Tests already fail in worktrees. Repo rename would break more.

#### J. Hermes Profile Adapter Implementation Plan
- **Status:** Mentioned in both migration doc and adapter contract.
- **Gap:** No implementation plan for the `jarvis` Hermes profile split. No dry-run validation steps. No config template. No documentation for install/start/health/recovery of a second gateway.
- **Impact:** Profile split is aspirational, not actionable.

#### K. Portable Browser Recipe Provenance Tracking System
- **Status:** Defined in adapter contract (rules and limits).
- **Gap:** No actual tracking system. No `data/zeus/browser-recipes/` directory. No provenance JSON schema. No registration CLI. No `SKILL.md` provenance verification workflow.
- **Impact:** Browser recipes remain theoretical.

#### L. Adapter Manifest Schema Validation
- **Status:** Adapter contract defines a YAML manifest shape.
- **Gap:** No JSON Schema or Python dataclass for the manifest. No validation CLI. No adapter registry DB table.
- **Impact:** Cannot verify adapter compliance.

### 2.2 Summary of Gaps

| # | Missing Artifact | Severity | Blocking Phase |
|---|------------------|----------|----------------|
| A | Formal AS-IS architecture diagram | Medium | 1+ |
| B | Formal TO-BE architecture diagram | Medium | 1+ |
| C | Complete identity matrix (all surfaces) | High | 1 |
| D | Import/CLI compatibility test plan | High | 2 |
| E | Active automation inventory | High | 3 |
| F | Wiki migration plan with exact path mappings | High | 3-4 |
| G | Data backup/rollback procedures | Critical | 3+ |
| H | Zeus CLI parser drift fix plan | High | 1-2 |
| I | Path-hardcoding audit remediation plan | High | 1-2 |
| J | Hermes profile adapter implementation plan | Medium | 3+ |
| K | Browser recipe provenance tracking system | Low | 4 |
| L | Adapter manifest schema validation | Low | 4 |

---

## 3. Stage / Substage Plan: From Current State to Safe ZeusOS Implementation

### Phase Legend
- **Phase 0** = Contract freeze (DONE)
- **Phase 1** = Rename-blocker cleanup + compatibility groundwork
- **Phase 2** = Additive aliases + compatibility tests
- **Phase 3** = Operator migration (systemd, automation inventory)
- **Phase 4** = Wiki and public rename
- **Phase 5** = Hermes profile adapter + external repo contracts

---

### Stage 1.0: Zeus CLI Parser Deduplication
**Objective:** Eliminate the duplicated `build_zeus_parser()` definitions.
**Current state:** Two near-identical parser trees in `src/jinwang_jarvis/cli.py` (lines 331-428) and `src/jinwang_jarvis/zeus_os/cli.py` (lines 14-114). The `cli.py` version wraps the `zeus_os/cli.py` version via `build_zeus_parser(zeus_subparsers)`.
**Side-effect class:** `local_repo_write` (modifies `src/jinwang_jarvis/cli.py` and `src/jinwang_jarvis/zeus_os/cli.py`).
**Required approval:** `repo_write` (Jinwang + external-contractor review).

#### Acceptance Criteria
1. Only one canonical `build_zeus_parser()` exists (in `zeus_os/cli.py`).
2. `src/jinwang_jarvis/cli.py` imports and delegates to it without redefining subparsers.
3. `PYTHONPATH=src python -m jinwang_jarvis.cli zeus --help` produces identical output before and after.
4. `PYTHONPATH=src pytest -q tests/test_zeus_cli.py` passes.
5. `PYTHONPATH=src pytest -q` (full suite) passes.

#### Tests
- Regression test: capture `--help` output for `zeus init`, `zeus task submit`, `zeus boardroom create` before change; diff after.
- Unit test: verify all zeus subcommands are registered.

#### Alignment Scoring Rubric (>=95% required)
| Criterion | Weight | How to Score |
|---|---|---|
| Parser output identical | 40% | `diff` of `--help` outputs = empty |
| All Zeus tests pass | 30% | `pytest tests/test_zeus_*.py` = 0 failures |
| Full suite passes | 20% | `pytest -q` = 0 failures |
| No Hermes touch | 10% | `git diff` shows no changes outside `src/jinwang_jarvis/` |

---

### Stage 1.1: Path-Hardcoding Remediation
**Objective:** Remove unsafe `/home/jinwang/workspace/jinwang-jarvis` assumptions and make workspace-root-driven defaults.
**Current state:**
- `tests/test_config.py`: 10 hardcoded absolute path assertions (fails in worktrees already).
- `styled_voice_samples.py`: `DEFAULT_SAMPLE_LIBRARY_DIR` hardcodes `~/workspace/jinwang-jarvis/data/styled-voice-samples`.
- `knowledge.py`: `WATCHLIST_NOTE_RELATIVE_PATH`, `MEMORY_NOTE_DIR` hardcode `jinwang-jarvis-*`.
- `intelligence.py`: `INTELLIGENCE_NOTE_DIR` hardcodes `jinwang-jarvis-intelligence`.
**Side-effect class:** `local_repo_write`.
**Required approval:** `repo_write`.

#### Acceptance Criteria
1. `tests/test_config.py` uses `tmp_path` or `Path.cwd()`-relative assertions, not `/home/jinwang/workspace/jinwang-jarvis`.
2. `styled_voice_samples.py` default becomes relative to `workspace_root` config or env var, not hardcoded home path.
3. `knowledge.py` and `intelligence.py` path constants become config-driven or accept an override parameter.
4. Full test suite passes.
5. `python -m compileall -q src/jinwang_jarvis` is clean.

#### Tests
- `pytest tests/test_config.py` passes from a non-default worktree path.
- `pytest tests/` passes when run from `/tmp/zeusos-test-worktree/`.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| test_config passes in worktree | 30% | Run in `/tmp/` worktree; 0 failures |
| styled_voice path is config-driven | 25% | Code review confirms no hardcoded `~/workspace/jinwang-jarvis` |
| knowledge/intelligence paths config-driven | 25% | Code review confirms config override exists |
| Full suite passes | 15% | `pytest -q` = 0 failures |
| No runtime behavior change | 5% | Existing `pipeline.local.yaml` produces same output |

---

### Stage 1.2: Identity Matrix Completion
**Objective:** Produce a comprehensive, machine-verifiable inventory of every surface referencing `jinwang-jarvis` / `jinwang_jarvis` / `jarvis` with a classified decision.
**Current state:** Partial matrix in `docs/zeus-os-rebrand-migration.md` covers 11 surfaces.
**Side-effect class:** `local_artifact_write` (new doc only).
**Required approval:** `repo_write` (doc review).

#### Acceptance Criteria
1. Document covers >=95% of all `jinwang` string occurrences in the repo (excluding `.git/`, `.venv/`, `__pycache__/`, historical `orchestration/`).
2. Every entry classified as: `keep`, `alias`, `deprecate`, `profile-split`, or `rename-later`.
3. Entries include: file path, line number, current value, target value, phase decision, risk level.
4. Document is committed to `docs/zeus-os-identity-matrix.md`.

#### Tests
- Automated check: `grep -r "jinwang" --include="*.py" --include="*.md" --include="*.yaml" --include="*.toml" src/ docs/ config/ scripts/ systemd/ tests/ | wc -l` must match documented count within 5%.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| Coverage >=95% of occurrences | 40% | Automated grep count vs documented count |
| Every entry classified | 30% | Manual spot-check 20 entries |
| Includes line numbers | 15% | Doc review |
| Committed to repo | 15% | `git log` shows doc commit |

---

### Stage 2.0: Import / CLI Compatibility Test Plan
**Objective:** Prove old and new import/CLI paths work together before deprecating anything.
**Current state:** No test plan exists.
**Side-effect class:** `local_repo_write` (new tests/docs).
**Required approval:** `repo_write`.

#### Acceptance Criteria
1. Test fixture demonstrates `from jinwang_jarvis.zeus_os import schema` works (current).
2. Test fixture demonstrates `from zeus_os import schema` works (future alias).
3. Test fixture demonstrates `python -m jinwang_jarvis.cli zeus init` works.
4. Test fixture demonstrates `python -m zeus_os.cli zeus init` works (future alias).
5. Document specifies how to run compatibility tests in CI.

#### Tests
- New file: `tests/test_zeus_compatibility.py` with parameterized import tests.
- New file: `tests/test_zeus_cli_aliases.py` with subprocess CLI tests.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| Import shim tests pass | 35% | `pytest tests/test_zeus_compatibility.py` |
| CLI alias tests pass | 35% | `pytest tests/test_zeus_cli_aliases.py` |
| CI documentation exists | 20% | Doc review |
| No existing test breakage | 10% | `pytest -q` = 0 failures |

---

### Stage 2.1: Additive Alias Introduction (CLI + Import)
**Objective:** Add `zeus-os` CLI entry point and `zeus_os` import shim while keeping existing names working.
**Current state:** Only `jinwang-jarvis` CLI and `jinwang_jarvis` import exist.
**Side-effect class:** `local_repo_write`, `local_artifact_write` (shim files).
**Required approval:** `repo_write` + `gateway_systemd` review (if any systemd ExecStart lines change).

#### Acceptance Criteria
1. `pyproject.toml` adds `zeus-os = "jinwang_jarvis.cli:main"` console script (or equivalent).
2. `src/zeus_os/__init__.py` created as a re-export shim from `jinwang_jarvis`.
3. `zeus-os --help` produces identical output to `jinwang-jarvis --help`.
4. `python -m zeus_os.cli zeus init` works.
5. All existing commands continue to work unchanged.
6. No systemd units modified (only templates/scripts may reference new name optionally).

#### Tests
- `tests/test_zeus_compatibility.py` validates both import paths.
- `tests/test_zeus_cli_aliases.py` validates both CLI names.
- Manual QA: `pip install -e .` then run both CLIs.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| Both CLIs produce identical help | 30% | `diff <(jinwang-jarvis --help) <(zeus-os --help)` |
| Both module paths work | 25% | `python -c "from jinwang_jarvis.zeus_os import schema; from zeus_os import schema"` |
| Full test suite passes | 20% | `pytest -q` = 0 failures |
| No systemd change | 15% | `git diff` shows no `systemd/` changes |
| Hermes untouched | 10% | `git diff` shows no `~/.hermes/` or Hermes source changes |

---

### Stage 3.0: Active Automation Inventory
**Objective:** Document all live automation before touching systemd/cron/plugin paths.
**Current state:** No inventory exists.
**Side-effect class:** `local_artifact_write` (documentation only, but requires live system inspection).
**Required approval:** `credential_access` (to inspect `~/.config/systemd/user/`, `~/.hermes/config.yaml`), `repo_write`.

#### Acceptance Criteria
1. Inventory document lists all `systemctl --user` timers and services.
2. Inventory document lists all Hermes cron jobs from `config.yaml`.
3. Inventory document lists all plugin symlinks in `~/.hermes/plugins/`.
4. Inventory document lists all active config paths.
5. Document is committed to `orchestration/2026-05-07-zeusos-end-to-end-gated/03-automation-inventory/`.

#### Tests
- Verification: run `systemctl --user list-timers --all` and diff against inventory.
- Verification: check `~/.hermes/plugins/` symlink targets.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| All timers documented | 30% | `systemctl` output matches doc |
| All cron jobs documented | 25% | `config.yaml` cron section matches doc |
| All plugin symlinks documented | 25% | `ls -la ~/.hermes/plugins/` matches doc |
| No system changes made | 20% | `git status` clean outside orchestration/ |

---

### Stage 3.1: Systemd Unit Alias / Migration
**Objective:** Introduce `zeusos-*` systemd unit variants alongside existing `jinwang-jarvis-*` units.
**Current state:** 7 unit files, all prefixed `jinwang-jarvis-` except `hermes-gateway.service`.
**Side-effect class:** `gateway_systemd` (high risk — touches live automation).
**Required approval:** `gateway_systemd` + Jinwang explicit approval + staging validation.

#### Acceptance Criteria
1. New unit files `zeusos-cycle.service`, `zeusos-cycle.timer`, etc. created in `systemd/`.
2. `scripts/install.sh` updated with `--product-name` flag (default remains `jinwang-jarvis`).
3. `src/jinwang_jarvis/runtime.py` constants updated to support both name families.
4. Old units remain untouched; new units are **not** enabled until Stage 3.2.
5. `systemctl --user daemon-reload` is **not** required at this stage (files only rendered).

#### Tests
- `scripts/install.sh --product-name zeusos --workspace-only` generates correct unit files.
- `scripts/install.sh --product-name jinwang-jarvis --workspace-only` generates original unit files.
- `python -m compileall -q src/jinwang_jarvis/runtime.py` clean.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| Both unit families render correctly | 30% | File diff review |
| Default behavior unchanged | 25% | `install.sh` without flag produces old names |
| No live systemd state changed | 25% | `systemctl` status identical before/after |
| Full test suite passes | 15% | `pytest -q` = 0 failures |
| Hermes gateway untouched | 5% | No `hermes-gateway.service` changes |

---

### Stage 3.2: Operator Cutover (Disable Old / Enable New)
**Objective:** Atomically switch from old units to new units with rollback capability.
**Side-effect class:** `gateway_systemd` (HIGHEST RISK — live automation cutover).
**Required approval:** `gateway_systemd` + Jinwang + MoA alignment >=95%.

#### Acceptance Criteria
1. Old units disabled (`systemctl --user disable jinwang-jarvis-cycle.timer` etc.).
2. New units enabled (`systemctl --user enable zeusos-cycle.timer` etc.).
3. `systemctl --user daemon-reload` executed.
4. Rollback script tested and committed.
5. Pipeline cycle runs successfully under new units.

#### Tests
- Dry-run: `install.sh --dry-run` shows disable/enable plan.
- Live: Run one `zeusos-cycle.service` manually; verify output.
- Rollback: Run rollback script; verify old units re-enabled.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| New units run successfully | 35% | Manual service run produces expected artifacts |
| Old units cleanly disabled | 25% | `systemctl --user list-timers` shows only new |
| Rollback script works | 25% | Rollback restores old units and they run |
| No duplicate timers | 10% | No ghost timers observed |
| Hermes gateway unaffected | 5% | Gateway status unchanged |

---

### Stage 4.0: Wiki Path Migration
**Objective:** Rename generated wiki paths from `jinwang-jarvis-*` to `zeusos-*` with redirects.
**Current state:** `queries/jinwang-jarvis-importance-shift-watchlist.md`, `queries/jinwang-jarvis-memory/`, `queries/jinwang-jarvis-intelligence/`, etc.
**Side-effect class:** `local_artifact_write` (wiki files), `repo_write` (source constants).
**Required approval:** `repo_write` + Jinwang (wiki is personal knowledge graph).

#### Acceptance Criteria
1. Source constants in `knowledge.py`, `intelligence.py`, `wiki_contract.py` updated.
2. Wiki files renamed with symlink redirects from old paths.
3. `wiki-semantic-lint` passes with zero generated/canonical boundary errors.
4. No `raw/` content mutated.
5. Old paths remain accessible for >=30 days.

#### Tests
- `PYTHONPATH=src python3 -m jinwang_jarvis.cli wiki-semantic-lint --wiki-root /home/jinwang/wiki` passes.
- `ls -la wiki/queries/` shows symlinks for old names.
- Full pipeline cycle generates notes at new paths.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| Semantic lint passes | 30% | JSON output shows `ok: true` |
| Old paths still resolve | 25% | `ls` confirms symlinks exist |
| New paths generated correctly | 25% | Pipeline run creates new-path artifacts |
| No raw/ mutation | 15% | `git diff wiki/raw/` empty |
| Full suite passes | 5% | `pytest -q` = 0 failures |

---

### Stage 4.1: Public Docs / README Rename
**Objective:** Complete public-facing identity migration.
**Side-effect class:** `local_repo_write` (docs only).
**Required approval:** `repo_write`.

#### Acceptance Criteria
1. `README.md` shows `zeus-os` CLI as primary, `jinwang-jarvis` as legacy alias.
2. All `docs/*.md` updated with new CLI examples.
3. `Spec.md` title updated.
4. `skills/*/SKILL.md` updated.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| README primary identity = ZeusOS | 30% | Doc review |
| All docs reference new CLI | 30% | `grep -r "jinwang-jarvis" docs/` count <= legacy references only |
| SKILL.md files updated | 25% | Spot-check 3 skills |
| No runtime change | 15% | `git diff` shows no `src/` changes |

---

### Stage 5.0: Hermes Profile Adapter (Jarvis Profile Split)
**Objective:** Implement the `jarvis` Hermes profile for mail/calendar/news/report work.
**Current state:** Conceptual only; no implementation.
**Side-effect class:** `gateway_systemd` (new gateway deployment), `credential_access` (new config).
**Required approval:** `gateway_systemd` + Jinwang + staging validation.

#### Acceptance Criteria
1. Profile config template created (`config/hermes-profile-jarvis.yaml` or equivalent).
2. Documentation for install/start/health/recovery of `jarvis` profile gateway.
3. Dry-run validation: profile loads without errors.
4. Does **not** rename `default` / Boramae profile.
5. Does **not** require Hermes source changes.

#### Tests
- Dry-run: `hermes-gateway --config config/hermes-profile-jarvis.yaml --dry-run` (or equivalent).
- Health: New gateway responds to health check.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| Config template valid | 30% | Dry-run passes |
| Docs complete | 25% | Install/start/health/recovery documented |
| Default profile untouched | 25% | Existing gateway unaffected |
| Hermes source untouched | 20% | `git diff ~/.hermes/hermes-agent/` empty |

---

### Stage 5.1: External Repo Adapter Contract Implementation
**Objective:** Implement adapter manifest validation and first adapter (K-Skill or other).
**Side-effect class:** `local_repo_write`, `local_artifact_write`.
**Required approval:** `repo_write`.

#### Acceptance Criteria
1. Adapter manifest dataclass / JSON Schema created.
2. `zeus adapter validate <manifest.yaml>` CLI works.
3. First adapter manifest committed (e.g., `adapters/k-skill/contract.yaml`).
4. Adapter registry DB table or JSON index created.

#### Alignment Scoring Rubric
| Criterion | Weight | How to Score |
|---|---|---|
| Manifest validation works | 40% | CLI test passes |
| First adapter committed | 30% | File exists and validates |
| Registry tracks adapters | 20% | DB/query shows adapter |
| No external repo vendoring | 10% | No `git subtree` or copied code |

---

## 4. First Safe Substage to Implement Immediately

### Winner: Stage 1.0 (Zeus CLI Parser Deduplication)

**Why this is safe NOW:**
1. **No Hermes touch:** Only modifies `src/jinwang_jarvis/cli.py` and `src/jinwang_jarvis/zeus_os/cli.py`.
2. **No systemd touch:** No units changed, no daemon-reload needed.
3. **No gateway restart:** No config changes.
4. **No big-bang rename:** Import paths unchanged; `jinwang_jarvis` remains canonical.
5. **Compatibility preserved:** Existing `python -m jinwang_jarvis.cli zeus ...` calls work identically.
6. **Unblocks everything downstream:** Without this fix, any Zeus CLI enhancement must be duplicated, guaranteeing drift.

**Why NOT Stage 1.1 first:** Path remediation is also safe, but parser deduplication is a **precondition** for safe alias introduction (Stage 2.1). If we add aliases before deduplicating, we risk triplicating parser definitions.

**Why NOT Stage 2.1 first:** The converged verdict **explicitly rejects** adding aliases in the first PR. Aliases must wait until rename blockers are fixed.

**Implementation sketch:**
- Delete `build_zeus_parser()` from `src/jinwang_jarvis/cli.py`.
- Import `build_zeus_parser` from `jinwang_jarvis.zeus_os.cli` and call it with `zeus_subparsers`.
- Verify `handle_zeus` dispatch still works.
- Run full test suite.

---

## 5. FINAL_GATE_SCORE

### Alignment Assessment: Can We Move Beyond Replay Audit?

| Criterion | Score | Notes |
|---|---|---|
| **Contract clarity** | 95/100 | Migration contract and adapter contract are well-defined. Taxonomy is clear. |
| **AS-IS coverage** | 65/100 | No formal AS-IS diagram. Impact audit covers files but not runtime topology. |
| **TO-BE coverage** | 60/100 | No formal TO-BE diagram. Target state described in prose only. |
| **Identity matrix completeness** | 55/100 | Partial matrix exists. Missing import-level, generator-metadata, and SKILL.md coverage. |
| **Gate definitions** | 70/100 | Gates listed but not all have explicit test plans or acceptance criteria. |
| **Parser drift fix** | 50/100 | Identified as blocker but no implementation yet. |
| **Path hardcoding fix** | 50/100 | Identified as blocker but no implementation yet. |
| **Active automation inventory** | 30/100 | Not produced. Cannot safely touch systemd without it. |
| **Wiki migration plan** | 40/100 | Mentioned but no exact path mapping or symlink strategy. |
| **Data backup/rollback** | 30/100 | Mentioned but no explicit procedures or scripts. |
| **Hermes profile plan** | 35/100 | Conceptual; no config template or dry-run steps. |
| **Browser recipe provenance** | 20/100 | Rules defined; no tracking system. |
| **Test infrastructure for aliases** | 25/100 | No compatibility tests exist yet. |

### FINAL_GATE_SCORE: **54/100**

### Verdict: **FAIL**

**We cannot move beyond replay audit at this time.**

**Why:** The contracts and taxonomy are strong (Phase 0 is genuinely complete), but the implementation prerequisites for even Stage 1 are incomplete. Specifically:

1. **No parser drift fix exists yet** (Stage 1.0 blocking).
2. **No path-hardcoding fix exists yet** (Stage 1.1 blocking).
3. **No identity matrix covers all surfaces** (Stage 1.2 blocking).
4. **No compatibility test plan exists** (Stage 2.0 blocking).
5. **No active automation inventory exists** (Stage 3.0 blocking — this is a hard safety gate).

### Required to Achieve PASS (>=95% alignment):

**Minimum threshold for moving to Stage 1.0 implementation:**
1. Complete Stage 1.2 (identity matrix) — raises AS-IS/TO-BE coverage to >=90%.
2. Implement Stage 1.0 (parser deduplication) with passing tests.
3. Implement Stage 1.1 (path hardcoding remediation) with passing tests.
4. Produce Stage 2.0 (compatibility test plan) as a committed document with executable fixtures.

**Estimated score after completing 1.0 + 1.1 + 1.2 + 2.0:** ~85-90/100.

**Minimum threshold for moving to Stage 2.1 (alias introduction):**
5. All of the above, PLUS external-contractor + MoA review of the identity matrix and test results.
6. Hermes no-touch verification signed off.

**Minimum threshold for moving to Stage 3.0+ (systemd/automation touch):**
7. Stage 3.0 (active automation inventory) completed and verified against live system.
8. Stage G (data backup/rollback procedures) documented and tested.

---

## 6. Appendices

### Appendix A: Committed Decisions Evidence

| Commit | File | Decision |
|---|---|---|
| `1a70959` | `docs/zeus-os-rebrand-migration.md` | Compatibility-first migration contract |
| `05d7b12` | `docs/zeus-os-adapter-contract.md` | External adapter boundaries and provenance rules |
| `1a70959` | `README.md` | ZeusOS product identity, Jarvis capability-pack, `jinwang-jarvis` compatibility |

### Appendix B: Existing Orchestration Artifacts Referenced

| Path | Content |
|---|---|
| `orchestration/2026-05-06-zeusos-converge/converged-controller-verdict.md` | MoA convergence: docs-first PR, no big-bang rename |
| `orchestration/2026-05-06-zeusos-converge/01-rebrand-migration-plan/result.md` | Lane #1: 4-phase migration plan |
| `orchestration/2026-05-06-zeusos-converge/02-repo-rename-impact-audit/result.md` | Lane #2: >=130 files, 11 breakage categories |
| `orchestration/2026-05-05-opencode-zeus-os-foundation/result.md` | Zeus OS foundation: 13 modules, 72 tests, plugin |

### Appendix C: Current Hardcoded Path Inventory (Confirmed)

| File | Line(s) | Hardcoded Value | Risk |
|---|---|---|---|
| `tests/test_config.py` | 12-24 | `/home/jinwang/workspace/jinwang-jarvis` (10x) | Fails in worktrees |
| `src/jinwang_jarvis/styled_voice_samples.py` | 11-14 | `~/workspace/jinwang-jarvis/data/styled-voice-samples` | Breaks on repo rename |
| `src/jinwang_jarvis/knowledge.py` | 13-24 | `queries/jinwang-jarvis-*`, `queries/jinwang-jarvis-memory/*` | Wiki link rot |
| `src/jinwang_jarvis/intelligence.py` | ~78 | `queries/jinwang-jarvis-intelligence` | Wiki link rot |
| `src/jinwang_jarvis/runtime.py` | 29-35 | `jinwang-jarvis-cycle.service`, etc. | systemd rename dependency |
| `src/jinwang_jarvis/cli.py` | 331-428 | Duplicate `build_zeus_parser()` | Maintenance drift |

### Appendix D: Live Systemd Units (Confirmed)

| Unit | Type | Rename Target |
|---|---|---|
| `jinwang-jarvis-cycle.service` | Service | `zeusos-cycle.service` (Stage 3.1+) |
| `jinwang-jarvis-cycle.timer` | Timer | `zeusos-cycle.timer` (Stage 3.1+) |
| `jinwang-jarvis-weekly-review.service` | Service | `zeusos-weekly-review.service` (Stage 3.1+) |
| `jinwang-jarvis-weekly-review.timer` | Timer | `zeusos-weekly-review.timer` (Stage 3.1+) |
| `jinwang-jarvis-hermes-health.service` | Service | `zeusos-hermes-health.service` (Stage 3.1+) |
| `jinwang-jarvis-hermes-health.timer` | Timer | `zeusos-hermes-health.timer` (Stage 3.1+) |
| `hermes-gateway.service` | Service | **NEVER RENAME** |

---

*End of audit. This document is a read-only analysis artifact. No production source files were modified during its creation.*
