# Stage 05 Gate — Adapter Manifest + Browser Recipe Dry-Run

**Stage:** `05-adapter-recipe`  
**Mode:** additive dry-run adapter contract implementation.  
**Allowed by:** Stages 00-04 PASS.

## Diff scope

- `src/jinwang_jarvis/zeus_os/adapters.py`
  - adapter manifest validation
  - browser recipe validation
  - dry-run proposal construction
  - registered internal artifact write
  - secret/private-field rejection and redaction in returned payloads
  - missing-task preflight before filesystem write
  - per-run unique artifact names
  - post-write DB registration failure cleanup
- `src/jinwang_jarvis/zeus_os/cli.py`
  - `zeus adapter dry-run` subcommand
- `tests/test_zeus_adapters.py`
  - valid dry-run proposal tests
  - missing-task no-file tests
  - password/private-field redaction tests
  - repeated dry-run artifact reconciliation tests

## Stop lines preserved

- No browser execution.
- No external repo mutation.
- No Hermes config/runtime/gateway/systemd mutation.
- No live helper patch promotion.
- No credential/cookie/localStorage persistence as reusable recipe truth.

## External/MoA review loop

### Review round 1

- Reviewer A: **FAIL 82/100**
  - Missing `task_id` wrote an unregistered filesystem artifact before FK failure.
- Reviewer B: **FAIL 82/100**
  - Sensitive recipe values could be persisted.
  - Missing post-write registration cleanup.
  - `side_effects: []` wording overclaimed because local artifact/DB side effect exists.

### Remediation 1

- Added task existence preflight before artifact write.
- Added sensitive-field and secret-like validation.
- Changed successful proposal from ambiguous `side_effects: []` to:
  - `external_side_effects: []`
  - `local_side_effects: ["register_internal_artifact"]`
- Added tests for invalid/missing task and sensitive-field recipe.

### Review round 2

- Reviewer A: **PASS 96/100**
- Reviewer B: **FAIL ~88-92/100**
  - Duplicate dry-runs reused the same artifact URI and caused hash mismatch.
  - Rejected password values were still returned unredacted in CLI payload.
  - DB registration failure after file write could leave unregistered files.

### Remediation 2

- Added `_redact_sensitive_fields()` so rejected payload echoes do not expose arbitrary sensitive-key values.
- Added per-run unique artifact names: `adapter-browser-recipe-dry-run-<id>.json`.
- Added cleanup if `artifacts.register_artifact()` fails after file write.
- Added regression tests for duplicate dry-run reconciliation and redacted rejected password values.

### Final adversarial review

- External adversarial reviewer: **PASS 97/100**
- Evidence:
  - duplicate dry-runs produce distinct artifact URIs
  - `reconcile_artifacts()` reports no unregistered files/hash mismatches
  - password-bearing recipe rejected and literal secret absent from serialized result
  - missing task writes no artifact file
  - monkeypatched post-write DB failure cleans up JSON artifact
  - full suite in reviewer lane: `390 passed`

## Controller verification

Focused controller command:

```bash
PYTHONPATH=src python -m pytest tests/test_zeus_adapters.py tests/test_zeus_cli.py tests/test_zeus_worker.py tests/test_zeus_path_audit.py -q
```

Result before final review: `27 passed`.

## Gate score

**97/100 — PASS**

## Next allowed stage

Proceed to final full verification, repo diff audit, commit, and concise report.
