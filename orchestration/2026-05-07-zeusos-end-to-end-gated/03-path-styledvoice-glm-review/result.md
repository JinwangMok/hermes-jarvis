# Phase 1.2/1.3 Path & Styled-Voice Config Cleanup — GLM Review

**Reviewer**: GLM-5.1 (Sisyphus orchestration)
**Date**: 2026-05-07
**Diff scope**: 6 files changed, 130 insertions(+), 117 deletions(-)
**Constraint baseline**: compatibility-first, no repo rename, no zeusos alias, no Hermes/systemd/wiki/external repo mutation, no gateway restart

---

## Summary

The diff removes the hardcoded `~/workspace/jinwang-jarvis/data/styled-voice-samples` default from `styled_voice_samples.py` and its fallback copy in `styled_voice_request.py`, replacing it with a 3-tier dynamic resolution function (`default_sample_library_dir()`). It also deduplicates the Zeus CLI parser definitions (Phase 1.1 spillover). All 23 affected tests pass. No constraints are violated. The core objective is fully met, but two acceptance-criteria-required tests are missing.

---

## Files Changed

| File | Change | Phase |
|---|---|---|
| `src/jinwang_jarvis/styled_voice_samples.py` | Replace hardcoded path with `default_sample_library_dir()`, add `_sample_library_base()` helper | 1.3 |
| `skills/styled-voice/scripts/styled_voice_request.py` | Mirror fallback with same 3-tier resolution | 1.3 |
| `src/jinwang_jarvis/zeus_os/cli.py` | Extract `populate_zeus_subparsers()` as single source of truth | 1.1 |
| `src/jinwang_jarvis/cli.py` | Replace duplicated ~100-line parser with `populate_zeus_subparsers()` call | 1.1 |
| `tests/test_styled_voice_samples.py` | +2 tests for `default_sample_library_dir()` | 1.3 |
| `tests/test_zeus_cli.py` | +2 parser parity tests, +helper functions | 1.1 |

---

## Constraint Compliance

| Constraint | Status | Evidence |
|---|---|---|
| No repo rename | ✅ PASS | No file/directory renaming in diff |
| No zeusos alias | ✅ PASS | No alias added anywhere |
| No Hermes mutation | ✅ PASS | Zero changes to plugins/, hermes-*, gateway code |
| No systemd/wiki/external repo mutation | ✅ PASS | systemd/ untouched; wiki/ untouched; no external repo refs |
| No gateway restart | ✅ PASS | No gateway config or plugin changes |
| `repo_write` side-effect class only | ✅ PASS | Only source and test files modified |

---

## Blocking Issues

**None.**

---

## Important Issues

### I-1: Missing `JARVIS_WORKSPACE_ROOT` env var precedence test
- **Severity**: Important
- **Location**: `tests/test_styled_voice_samples.py`
- **Detail**: `default_sample_library_dir()` has a 3-tier precedence: (1) `JARVIS_STYLED_VOICE_SAMPLE_DIR`, (2) `JARVIS_WORKSPACE_ROOT` or supplied root, (3) `Path.cwd()`. Tests cover tiers 1 (explicit override) and 3 (workspace-root argument). **Tier 2 — `JARVIS_WORKSPACE_ROOT` env var as fallback when no argument is passed — is untested.**
- **Fix**: Add test:
  ```python
  def test_default_sample_library_dir_honors_workspace_root_env(tmp_path, monkeypatch):
      monkeypatch.delenv("JARVIS_STYLED_VOICE_SAMPLE_DIR", raising=False)
      monkeypatch.setenv("JARVIS_WORKSPACE_ROOT", str(tmp_path))
      assert default_sample_library_dir() == tmp_path / "data" / "styled-voice-samples"
  ```
- **Impact on score**: −3

### I-2: Missing Zeus source audit test (Phase 1.2 acceptance requirement)
- **Severity**: Important
- **Location**: Required by Phase 1.2 acceptance criteria: *"New audit test or script proving Zeus source has no absolute personal workspace path."*
- **Detail**: No such test exists. Grep confirms `src/jinwang_jarvis/zeus_os/` has zero `jinwang-jarvis` filesystem path references, so the condition is met in practice, but the acceptance criteria explicitly require a **test artifact**.
- **Fix**: Add to `tests/test_zeus_cli.py` or a new `tests/test_path_audit.py`:
  ```python
  def test_zeus_source_has_no_hardcoded_workspace_path():
      zeus_dir = Path(__file__).resolve().parent.parent / "src" / "jinwang_jarvis" / "zeus_os"
      hits = []
      for py in zeus_dir.rglob("*.py"):
          for i, line in enumerate(py.read_text().splitlines(), 1):
              if "jinwang-jarvis" in line and "jinwang-jarvis" not in ('"jinwang-jarvis"', "'jinwang-jarvis'"):
                  # allow only string literals that are user-agent/generator identifiers
                  continue
              if "workspace/jinwang-jarvis" in line or "~/workspace" in line:
                  hits.append(f"{py.relative_to(zeus_dir.parent.parent.parent)}:{i}: {line.strip()}")
      assert not hits, f"Hardcoded workspace paths found in Zeus source:\n" + "\n".join(hits)
  ```
- **Impact on score**: −5

### I-3: Phase scope mixing (1.1 + 1.2 + 1.3 in single diff)
- **Severity**: Low
- **Detail**: The diff title references "Phase 1.2 path/styled-voice config cleanup" but includes the complete Phase 1.1 CLI parser deduplication (~100 lines of `cli.py` removal + `zeus_os/cli.py` refactor). This makes isolated review harder.
- **Impact on score**: −2

### I-4: Fallback script minor parity gaps
- **Severity**: Low
- **Location**: `skills/styled-voice/scripts/styled_voice_request.py` fallback `collect_profile_audio` (lines 28–40)
- **Detail**:
  - Missing type annotation on `workspace_root` parameter (main module has `Path | str | None`).
  - Inline audio check doesn't guard `path.is_file()` or skip dotfiles, unlike the main `_is_audio_file()`.
  - Both are acceptable for a `# pragma: no cover` standalone fallback but create drift risk.
- **Impact on score**: −2

---

## Missing Tests

| ID | Description | Required By |
|---|---|---|
| MT-1 | `JARVIS_WORKSPACE_ROOT` env var precedence in `default_sample_library_dir()` | Implicit (3-tier function, 1 tier untested) |
| MT-2 | Zeus source audit: no hardcoded `/home/jinwang/workspace/jinwang-jarvis` | Phase 1.2 acceptance criteria (explicit) |
| MT-3 | Fallback `styled_voice_request.py` standalone behavior when PYTHONPATH unset | Best practice (not explicitly required) |

---

## Positive Findings

1. **Clean 3-tier resolution** — `JARVIS_STYLED_VOICE_SAMPLE_DIR` > `JARVIS_WORKSPACE_ROOT`/argument > `Path.cwd()` is the right precedence order.
2. **Backward compatible** — `DEFAULT_SAMPLE_LIBRARY_DIR` still exists as a module-level constant; existing callers are unaffected.
3. **`_sample_library_base()` centralization** — Eliminates the repeated `Path(library_dir).expanduser() if library_dir else DEFAULT_SAMPLE_LIBRARY_DIR` pattern across 5 call sites.
4. **Parser deduplication is correct** — `populate_zeus_subparsers()` as single source of truth prevents drift; parity test validates structural equality.
5. **Zero remaining `~/workspace` in src/** — Grep confirms `styled_voice_samples.py` and `styled_voice_request.py` no longer contain hardcoded workspace paths.
6. **No `test_config.py` changes** — Correct per Phase 1.2: "Non-Zeus tests that deliberately assert local default paths are classified as compatibility tests."

---

## Test Results

```
23 passed in 0.82s
  tests/test_styled_voice_samples.py — 8 passed (2 new)
  tests/test_zeus_cli.py — 15 passed (2 new)
```

All green. No skips, no xfail, no deletions.

---

## Hardcoded Path Inventory (post-diff)

| Location | Type | Status |
|---|---|---|
| `src/jinwang_jarvis/styled_voice_samples.py` | ~~`~/workspace/jinwang-jarvis/...`~~ | ✅ REMOVED |
| `skills/styled-voice/scripts/styled_voice_request.py` | ~~`~/workspace/jinwang-jarvis/...`~~ | ✅ REMOVED |
| `tests/test_config.py` | `/home/jinwang/workspace/jinwang-jarvis` (10x) | Out of scope (compatibility test) |
| `systemd/*.service` | `/home/jinwang/workspace/jinwang-jarvis` | Out of scope (Phase 1.2: "systemd untouched") |
| `config/pipeline.local.yaml` | `workspace_root: /home/jinwang/...` | Out of scope (local config) |
| `docs/*.md`, `orchestration/` | Various references | Documentation, not runtime |

---

## FINAL_GATE_SCORE: 87 / 100

### Score Breakdown

| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Core objective (hardcoded path removal + env override) | 100 | 40% | 40 |
| Fallback script update | 100 | 10% | 10 |
| Test coverage (2 of 3 tiers tested, audit test missing) | 75 | 20% | 15 |
| Acceptance criteria compliance (missing Zeus audit test) | 80 | 15% | 12 |
| Constraint compliance | 100 | 10% | 10 |
| Phase scope cleanliness | 100 | 5% | 0 (deduction applied below) |

**Subtotal**: 87
**Deductions**: I-1 (−3), I-2 (−5), I-3 (−2), I-4 (−2) applied above.

---

## Verdict: **FAIL**

Gate threshold: ≥95. Actual: 87.

### Remediation to PASS (≥95)

| Step | Raises score to | Effort |
|---|---|---|
| Add `JARVIS_WORKSPACE_ROOT` env var test (I-1) | 90 | 5 min |
| Add Zeus source audit test (I-2) | 95 | 10 min |
| _(Optional)_ Separate Phase 1.1 commit (I-3) | 97 | git only |

**Minimum remediation for PASS: I-1 + I-2.**

---

## Approved-by

_Review only — no approval until remediation is applied and score ≥95._
