# HOOO proposal UX evolve result

## Scope

Evolved the already-implemented HOOO proposal-driven interview UX after post-implementation review. This is a hardening pass on the HOOO UX axis, not the separate Jarvis information-collector architecture axis.

## Review findings addressed

1. **Seed gate was too permissive at the numeric threshold**
   - Previous behavior: with 5 required dimensions, resolving 4/5 produced `ambiguity_score == 0.2`, which met the old `<= 0.2` seed gate even though `permission` remained unresolved.
   - Evolved behavior: `seed_ready` now requires `unresolved == []` as well as the threshold, and `seed()` explicitly rejects any unresolved dimensions with an error naming them.

2. **Other / new opinion did not consume plain freeform replies**
   - Previous behavior: after `other_opinion`, only a structured `Scope: ...` style reply resolved the pending dimension; plain text became a note.
   - Evolved behavior: when `pending_freeform_dimension` is set and the next turn is plain freeform, it resolves exactly that pending dimension, clears the pending marker, and leaves other dimensions unresolved.

## Files changed in this evolve pass

- `src/jinwang_jarvis/houroboros.py`
  - `seed()` now blocks unresolved dimensions even when ambiguity equals threshold.
  - `_recompute_interview_gate()` now sets `seed_ready` only when no unresolved dimensions remain.
  - `_update_interview_state_from_turn()` now routes plain freeform text to `pending_freeform_dimension` when present.
- `tests/test_houroboros.py`
  - Added regression for `Other -> plain freeform reply` resolving only the pending dimension.
  - Added regression for 4/5 resolved dimensions at `ambiguity_score == 0.2` still blocking seed.
- `skills/hooo/SKILL.md`
  - Existing local skill note remains as operational learning for this pitfall/verification timeout.

## Verification

- `python -m compileall -q src/jinwang_jarvis tests` — passed.
- `PYTHONPATH=src pytest -q tests/test_houroboros.py tests/test_hooo_gateway_plugin.py` — `36 passed`.
- `PYTHONPATH=src pytest -q tests/test_houroboros.py tests/test_hooo_gateway_plugin.py tests/test_cli.py tests/test_runtime.py` — `55 passed`.
- `PYTHONPATH=src pytest -q` — `244 passed in 124.72s`.

## Remaining evolve backlog

- Discord gateway still needs a live message-route for normal replies in HOOO threads so `Other` freeform can be captured from Discord without manual CLI `hooo turn`.
- `render_mode: update_existing` is still not fully honored; current gateway posts new card messages, while stale click rejection protects state correctness.
- Per-run interaction handling is not transaction-locked; concurrent same-revision clicks should eventually get a per-run lock or transactional recheck.
- Gateway callback should avoid falling back to card target IDs for observed-origin validation.

## Classification

`complete / verified` for this evolve pass. Remaining items are separate hardening backlog, not blockers for the current local runtime correctness fix.
