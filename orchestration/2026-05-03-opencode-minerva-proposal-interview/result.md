# Minerva proposal-driven interview UX result

## Summary

Implemented the Minerva proposal-driven interview contract in the Jarvis-owned Minerva runtime. Unresolved interview cards now deterministically ask the next dimension in `scope -> acceptance -> constraint -> executor -> permission` order, render exactly three concrete `select_proposal` options plus an `other_opinion` path, and keep `continue_interview` only as a backward-compatible reducer action rather than the default unresolved card UX.

## Files changed

- `src/jinwang_jarvis/minerva.py`: added proposal catalog, proposal card model, per-dimension reducer updates, `other_opinion` routing, bounded custom_id parsing with run/revision/dimension/option identity, and stale/mismatch rejection through the existing interaction guard.
- `src/jinwang_jarvis/cli.py`: allowed `select_proposal` and `other_opinion` in `minerva interact` / `minerva interact`.
- `plugins/hermes_minerva_gateway/__init__.py`: updated card text rendering so proposal options and the Other expected reply are visible before fallback structured text prompts.
- `tests/test_minerva.py`: added regression coverage for proposal card shape, per-dimension option selection, Other routing, custom_id identity, seed gating, and stale/mismatch behavior.
- `tests/test_minerva_gateway_plugin.py`: updated gateway plugin expectations to nested proposal-button card payloads.
- `docs/minerva-workflow.md` and `docs/minerva-discord-gateway.md`: documented implemented runtime behavior without claiming live Discord click testing.
- `orchestration/2026-05-03-opencode-minerva-proposal-interview/result.md`: this deterministic result artifact.

Pre-existing dirty files preserved and not edited by this implementation: `skills/minerva/SKILL.md`, `skills/minerva/SKILL.md`, and `skills/minerva/references/live-smoke-and-cleanup.md`.

## Card JSON and interaction examples

Unresolved first card shape:

```json
{
  "card_revision": 1,
  "card": {
    "proposal_card": {
      "dimension": "scope",
      "proposals": [
        {"option_id": "a", "label": "Jarvis-owned implementation", "value": "Implement only Jarvis-owned Minerva/Minerva runtime, gateway bridge, tests, and necessary docs for this task."},
        {"option_id": "b", "label": "Seed and plan only", "value": "Produce a deterministic Minerva seed and implementation plan, without changing runtime behavior."},
        {"option_id": "c", "label": "Tests and contract only", "value": "Limit work to regression tests and contract documentation; defer runtime implementation."}
      ],
      "other": {"action": "other_opinion", "expected_reply": "Scope: <your value>"}
    },
    "buttons": ["select_proposal", "select_proposal", "select_proposal", "other_opinion"]
  }
}
```

Example proposal button custom_id:

```text
minerva:v2:select_proposal:minerva-20260503-47b9bb5fb435:r1:dscope:oa
```

Example sequence:

1. Start `/minerva <goal>` writes a scope proposal card.
2. Selecting option A records only `decisions.scope`, lowers ambiguity from `1.0` to `0.8`, and emits the acceptance proposal card.
3. Selecting proposal buttons for acceptance, constraint, executor, and permission reduces ambiguity to `0.0`, sets `seed_ready=true`, and then seed proposal is allowed.
4. Selecting Other records `pending_freeform_dimension=<dimension>` and emits another card for that same dimension; it does not resolve all ambiguity. A structured reply such as `Scope: <value>` resolves that one dimension.

## Verification run

- `python -m compileall -q src/jinwang_jarvis tests` — passed with no output.
- `PYTHONPATH=src pytest -q tests/test_minerva.py tests/test_minerva_gateway_plugin.py` — passed: `34 passed in 2.74s` after review fix.
- `PYTHONPATH=src pytest -q tests/test_minerva.py tests/test_minerva_gateway_plugin.py tests/test_cli.py tests/test_runtime.py` — passed: `53 passed in 51.20s` during controller re-run.
- `PYTHONPATH=src pytest -q` — passed after review fix: `242 passed in 129.03s`.
- Manual CLI QA: started a temporary Minerva run and selected the first proposal via `minerva interact --custom-id ...`; observed first actions `select_proposal/select_proposal/select_proposal/other_opinion`, resolved `scope` only, ambiguity `0.8`, and next dimension `acceptance`.
- Independent senior review found no critical blockers. One important state-consistency issue was fixed after review: selecting a proposal after an `Other` request now clears `pending_freeform_dimension` for that resolved dimension, with regression coverage.

## Remaining risks

- Live Discord button clicking was not performed by design; this change was verified through local runtime artifacts, reducer tests, plugin unit tests, and CLI manual QA only.
- Gateway callbacks remain process-local as documented; restart-persistent Discord component dispatch is still a separate hardening task.
