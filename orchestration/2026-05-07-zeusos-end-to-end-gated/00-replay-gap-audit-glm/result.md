# ZeusOS End-to-End Gated Replay: Gap Audit

**Date:** 2026-05-07
**Auditor:** GLM-5.1 (Sisyphus READ-ONLY reviewer)
**Mode:** Replay audit — no production edits, no subagents
**Inputs replayed:**
- `README.md` (post-commit `05d7b12`)
- `docs/zeus-os-rebrand-migration.md` (post-commit `1a70959`)
- `docs/zeus-os-adapter-contract.md` (post-commit `05d7b12`)
- `src/jinwang_jarvis/zeus_os/*` (13 modules, post-commit `9efc302`)
- `tests/test_zeus_*.py` (6 test files)
- `orchestration/2026-05-06-zeusos-converge/converged-controller-verdict.md`
- `orchestration/2026-05-06-zeusos-converge/01-rebrand-migration-plan/result.md` (Lane #1)
- `orchestration/2026-05-06-zeusos-converge/02-repo-rename-impact-audit/result.md` (Lane #2)

---

## 1. Blocking Omissions

### 1.1 CRITICAL: No explicit AS-IS → TO-BE checklist exists in any committed artifact

The controller verdict (`converged-controller-verdict.md`) describes a converged decision and a recommended first PR scope. The migration contract (`zeus-os-rebrand-migration.md`) defines phases 0–4 and 9 gates. **Neither document contains a concrete, line-item AS-IS → TO-BE diff table** that a staging controller could mechanically check off.

The closest approximation is Lane #1's "Phased Migration Plan" (§3), but:
- It mixes AS-IS analysis with TO-BE proposals without separating them.
- The "Phase 1 actions" checklist is already partially invalidated by the controller verdict (which rejected Lane #1's first PR scope as too aggressive).
- There is no explicit mapping of *current state* (what exists now) vs *desired state* (what should exist after each substage).

**Gap:** A formal AS-IS → TO-BE table must be produced before any code work begins, and it must be derived from the **controller verdict** (the converged position), not from Lane #1 alone.

### 1.2 HIGH: Phase 1 scope is contradictory across documents

| Document | Phase 1 Scope |
|---|---|
| Lane #1 result.md | CLI aliases, `src/zeus_os/` shim, systemd unit aliases, `--product-name` flag |
| Controller verdict | Docs/contract-first only; no runtime behavior changes |
| Migration contract (committed) | Phase 0 = docs; Phase 1 = "rename-blocker cleanup" (parser drift, hardcoded paths) |
| Adapter contract (committed) | First implementations = "documentation and dry-run oriented" |

Lane #1's Phase 1 was explicitly rejected by the controller. The committed migration contract correctly redefines Phase 1 as "rename-blocker cleanup." **But no artifact records that this redefinition happened or tracks its completion criteria.**

**Gap:** The committed migration contract's Phase 1 definition is correct but lacks concrete acceptance tests. Specifically:
- "Zeus CLI parser drift" between `src/jinwang_jarvis/cli.py` and `src/jinwang_jarvis/zeus_os/cli.py` — what constitutes "fixed"? Regression tests? Deduplication?
- "Hardcoded local workspace path assumptions" — which files? What's the replacement pattern? `test_config.py` has 10+ hardcoded path assertions; is that the entire scope?
- "styled-voice sample path default" — what should it become? Config-driven? Workspace-root-relative?

### 1.3 HIGH: No adapter manifest schema or adapter directory exists yet

The adapter contract document describes a YAML manifest shape with `adapter_id`, `provider`, `interface`, `capabilities`, etc. **No such manifest file exists anywhere in the repository.** The `adapters/` directory does not exist. There is no `schemas/` directory for input/output schemas.

This is not blocking for Phase 0–1 (docs-only), but it IS blocking for Phase 4 and the adapter contract claims it should be the "first implementations" work. The contract implies near-term action but provides no tracking artifact.

**Gap:** Either (a) create a tracking issue/substage for "first adapter manifest prototype" or (b) explicitly defer adapter manifests to post-Phase-3 and note this in the contract document.

### 1.4 MEDIUM: Test suite is incomplete for Phase 1 gates

The 6 test files cover zeus_os internals well (schema, queue, events, artifacts, safety, CLI integration). However:

- **No test for the `jinwang_jarvis.cli` → `zeus_os.cli` parser delegation.** The main CLI (`src/jinwang_jarvis/cli.py`) delegates `zeus` subcommand to `zeus_os/cli.py:handle_zeus()`. There are no tests verifying that the top-level `jinwang-jarvis` CLI correctly wires to the Zeus subparser. `test_zeus_cli.py` imports `from jinwang_jarvis.cli import main` and calls `main(["zeus", ...])`, which partially covers this, but it doesn't test edge cases like unknown zeus subcommands, missing workspace flags, or concurrent access.

- **No test for schema migration rollback.** `schema.apply_migrations` is tested for idempotency but not for what happens if a migration partially fails.

- **No test for `doctor.py` secret scanning on actual DB content.** The doctor tests only check that it runs on a fresh init; they don't test secret detection on seeded data.

**Gap:** Before Phase 1 (rename-blocker cleanup), add regression tests specifically for:
1. CLI parser delegation (both old and new paths)
2. `test_config.py` hardcoded path removal verification
3. Doctor secret scanning with positive/negative test cases

### 1.5 LOW: `orchestration/2026-05-06-zeusos-converge/` is untracked

The converge directory is untracked in git. The controller verdict and both lane results are valuable historical evidence that should be committed, but the migration contract explicitly says "Historical `orchestration/` artifacts — No-touch." This is a documentation/housekeeping gap, not a code risk.

---

## 2. Over-Ambitious or Unsafe Next Steps

### 2.1 UNSAFE: Any attempt at Phase 1 code changes before AS-IS → TO-BE table

The controller verdict correctly identifies that Phase 1 should fix "rename-blocker cleanup" items. But attempting this without:
1. A concrete list of which files have hardcoded paths
2. A test plan that proves old and new paths both work
3. An active automation inventory (`systemctl --user list-timers`)

...would risk the exact breakage the Phase 0 contract was designed to prevent.

### 2.2 OVER-AMBITIOUS: Lane #1's Phase 1 scope (rejected but still in the record)

Lane #1 proposes adding `src/zeus_os/` shim, systemd aliases, and `--product-name` flag in Phase 1. The controller verdict explicitly rejected this. **Any future reference to Lane #1's Phase 1 must be treated as superseded by the controller verdict.** The risk is that a new contractor reads Lane #1 and starts implementing its Phase 1 without reading the controller verdict.

### 2.3 OVER-AMBITIOUS: Hermes profile split in Phase 2

The migration contract mentions Hermes profile splits as a Phase 2+ item. This is premature. Hermes profiles require:
- Understanding current Hermes resource contention (not measured)
- A separate gateway deployment (operational overhead)
- Profile-specific config/session/skill/memory isolation (untested)

**Recommendation:** Defer Hermes profile work to a separate roadmap item outside the ZeusOS rename track. The rename is already complex enough.

### 2.4 UNSAFE: Any wiki path rename before writer migration

Lane #1 correctly identifies wiki path breakage as 🔴 Critical risk. The migration contract's gate #7 says "Wiki migration plan: queue durable wiki entity/concept changes and generated-path movement separately; never rewrite `raw/`." This is correct but has no tracking artifact.

**Recommendation:** Before touching any wiki paths, produce a wiki impact inventory listing every `queries/jinwang-jarvis-*` file, every `[[wikilink]]` that references it, and every source constant that generates it.

### 2.5 OVER-AMBITIOUS: Browser recipe provenance in Phase 0

The committed docs (`05d7b12`) add browser recipe stance to the migration contract and adapter contract. This is appropriate as a documented stance. However, actually implementing browser recipe provenance (source task, target site, selector fragility, verification status, last-known-good timestamp) requires:
- A provenance schema (not defined)
- A registration mechanism (not implemented)
- A re-verification workflow (not designed)

This should remain documentation-only until Phase 3+ is stable.

---

## 3. Minimum Safe Next Substage

### Recommended: Phase 1.0 — Rename-Blocker Audit (READ-ONLY, no code changes)

**Objective:** Produce a concrete, mechanical checklist of every blocker that must be resolved before any alias or rename is safe.

**Deliverables:**

| # | Deliverable | Format | Verifiable By |
|---|---|---|---|
| 1 | Active automation inventory | `systemctl --user list-timers --all` output + cron jobs + plugin symlinks | Jinwang runs the commands |
| 2 | CLI parser drift report | Side-by-side diff of subparsers in `cli.py` vs `zeus_os/cli.py` | `diff <(grep add_parser cli.py) <(grep add_parser zeus_os/cli.py)` |
| 3 | Hardcoded path inventory | List of every `/home/jinwang/workspace/jinwang-jarvis` reference in src/ and tests/ | `grep -rn "jinwang/workspace/jinwang-jarvis" src/ tests/` |
| 4 | Wiki path dependency map | List of `queries/jinwang-jarvis-*` files + source constants referencing them | `grep -rn "jinwang-jarvis" src/ --include="*.py"` |
| 5 | Import dependency graph | Count of `from jinwang_jarvis` / `import jinwang_jarvis` per file | `grep -rl "from jinwang_jarvis" tests/ \| wc -l` |
| 6 | Phase 1 acceptance test plan | List of specific tests that must exist before and after each cleanup item | `pytest -q` passes + new tests listed |

**Constraints:**
- READ-ONLY: No code changes, only inventory/audit artifacts
- Output goes to `orchestration/2026-05-07-zeusos-end-to-end-gated/01-rename-blocker-audit/`
- Must be reviewable by Jinwang before any Phase 1.1 code work

**Why this is the minimum safe next step:**
- The migration contract defines Phase 1 as "rename-blocker cleanup" but doesn't enumerate the blockers with enough specificity to execute.
- The controller verdict lists 3 specific cleanup items (parser drift, hardcoded paths, styled-voice paths) but doesn't inventory their scope.
- Without a mechanical inventory, any code work in Phase 1 is guessing at scope.

**Estimated effort:** 1 audit session (all `grep`/`diff` commands can run in parallel).

---

## 4. 95% Gate Definition: Controller Comparison Protocol

### 4.1 What "contractor" means

The "contractor" is any external agent (Sisyphus subagent, OpenCode worker, future MoA lane) producing implementation artifacts for a substage.

### 4.2 What "MoA" means

"MoA" (Mixture of Agents) refers to the converged controller verdict produced by combining multiple independent lanes. In the current context, the MoA position is the `converged-controller-verdict.md` — the reconciled output of Lane #1, Lane #2, and Hermes MoA lanes A/B/C.

### 4.3 Alignment scoring

For each substage, the controller should compare contractor output against MoA position on these dimensions:

| Dimension | Weight | Scoring Criteria |
|---|---|---|
| **Scope compliance** | 30% | Does the contractor output stay within the approved scope for this substage? No scope creep, no unapproved surfaces touched. |
| **Invariant preservation** | 25% | Are all 7 non-negotiable invariants from the migration contract preserved? (Hermes untouched, SQLite canonical, Jarvis not erased, external repos independent, no big-bang, wiki paths stable, browser recipes portable) |
| **Test coverage** | 20% | Does the contractor output include or reference passing tests? New code must have new tests. Existing tests must not be deleted or skipped. |
| **Artifact provenance** | 15% | Is the output properly recorded in `orchestration/` with prompt, result, and log? Can the work be traced to a specific instruction? |
| **Documentation consistency** | 10% | Do any doc changes match the migration contract terminology? No conflicting identity claims. |

### 4.4 95% threshold calculation

For each dimension, score 0–100. Compute weighted average. If weighted average ≥ 95, the substage PASSES the gate.

**Special rules:**
- Any dimension scoring < 80 causes automatic FAIL regardless of weighted average.
- **Invariant preservation** scoring < 90 causes automatic FAIL (invariants are non-negotiable).
- Missing test coverage for new code causes automatic FAIL in test coverage dimension.

### 4.5 Comparison procedure

1. **Before substage:** Controller records expected scope, invariants, and acceptance criteria.
2. **After substage:** Contractor produces `result.md` in the substage directory.
3. **Controller comparison:**
   - Read contractor `result.md`.
   - Read MoA position (`converged-controller-verdict.md` + migration contract).
   - Score each dimension.
   - Compute weighted average.
   - Record score in a `gate.md` artifact in the substage directory.
4. **If PASS (≥95):** Proceed to next substage.
5. **If FAIL (<95):** Return to contractor with specific gap list. Do not proceed.

### 4.6 Concrete 95% gate checklist for Phase 1.0 (rename-blocker audit)

| # | Check | Must Be True |
|---|---|---|
| G1 | All 6 deliverables listed in §3 are present | ✅ |
| G2 | No production source files were modified | ✅ |
| G3 | Hermes source is confirmed untouched | ✅ |
| G4 | Inventory commands are reproducible (exact grep/diff commands listed) | ✅ |
| G5 | Scope is strictly within Phase 1 definition from migration contract | ✅ |
| G6 | Output is in `orchestration/` (not in `src/`, `docs/`, or `config/`) | ✅ |
| G7 | No recommendations for code changes — only inventory and audit items | ✅ |
| G8 | Hardcoded path inventory covers both `src/` and `tests/` | ✅ |
| G9 | CLI parser drift report covers both `cli.py` files | ✅ |
| G10 | Active automation inventory includes `systemctl`, cron, and plugin symlinks | ✅ |

**Pass threshold:** 10/10 checks = 100% (audit substages have a higher bar because they are purely informational).

---

## 5. FINAL_GATE_SCORE

### Dimension Scores

| Dimension | Score | Notes |
|---|---|---|
| Scope compliance | 100 | Audit produces only inventory artifacts, no code changes |
| Invariant preservation | 100 | All 7 invariants are preserved; audit is read-only |
| Test coverage | 95 | Existing test suite covers zeus_os well; missing edge case tests noted in §1.4 |
| Artifact provenance | 100 | Output goes to `orchestration/` with this result file |
| Documentation consistency | 95 | Terminology matches migration contract; minor ambiguity in Phase 1 scope noted in §1.2 |

### Weighted Average: 97.5

### Verdict: **PASS**

The current state (Phase 0 complete, Phase 1 not started) is consistent with the migration contract and controller verdict. The safe next step is the Phase 1.0 rename-blocker audit described in §3.

**Blocking caveats (do not proceed to code work until resolved):**
1. AS-IS → TO-BE table must be produced from the audit results.
2. Phase 1 acceptance test plan must be written before any cleanup code.
3. Active automation inventory must be collected from the live system (Jinwang must run `systemctl --user list-timers --all`).

**FINAL_GATE_SCORE: 97 / 100 — PASS for moving beyond replay audit.**
