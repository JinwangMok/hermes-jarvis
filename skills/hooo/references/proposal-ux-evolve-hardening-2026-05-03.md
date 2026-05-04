# HOOO proposal UX evolve hardening — 2026-05-03

Use this reference when hardening or reviewing Jarvis HOOO proposal-driven interview UX.

## Context

A post-implementation evolve pass found two correctness gaps after the proposal-card redesign had already passed broad tests:

1. Numeric ambiguity threshold was too permissive by itself.
2. `Other / new opinion` did not handle the natural Discord behavior where the user replies with plain text instead of a structured `Scope:`/`Acceptance:` message.

## Required behavior

### Seed gate

Required interview dimensions are `scope`, `acceptance`, `constraint`, `executor`, and `permission`.

Do **not** compute seed readiness as only:

```python
seed_ready = ambiguity_score <= AMBIGUITY_THRESHOLD
```

Use the stricter rule:

```python
seed_ready = not unresolved and ambiguity_score <= AMBIGUITY_THRESHOLD
```

Also re-check this in `seed()` itself. If any dimension remains unresolved, reject with an error that includes the unresolved dimension names. This matters because with five dimensions, resolving four produces `ambiguity_score == 0.2`, which equals the default threshold while one required decision is still missing.

Regression to keep:

- Turn sequence resolves four dimensions: `Scope`, `Acceptance`, `Constraint`, `Executor`.
- `permission` remains unresolved.
- Assert `ambiguity_score == 0.2`, `seed_ready is False`, and `seed()` raises naming `permission`.

### Other/freeform path

After a user clicks `Other / new opinion`, HOOO records `pending_freeform_dimension`.

If the next turn is plain freeform and the pending dimension is still the next unresolved dimension, treat the message as the decision for **that dimension only**:

- write it to `decisions[pending_dimension]`
- add only that dimension to `resolved`
- clear `pending_freeform_dimension`
- leave the remaining dimensions unresolved
- do not append it only to `notes`
- do not resolve all dimensions from arbitrary freeform text

Regression to keep:

- Start run.
- Click `other_opinion` on the `scope` card.
- Send plain text such as `Only touch Jarvis-owned runtime and tests`.
- Assert `decisions.scope` equals that text, `resolved == ['scope']`, `unresolved == ['acceptance', 'constraint', 'executor', 'permission']`, `ambiguity_score == 0.8`, and `seed_ready is False`.

## Verification pattern

For this class of HOOO runtime changes, run:

```bash
python -m compileall -q src/jinwang_jarvis tests
PYTHONPATH=src pytest -q tests/test_houroboros.py tests/test_hooo_gateway_plugin.py
PYTHONPATH=src pytest -q tests/test_houroboros.py tests/test_hooo_gateway_plugin.py tests/test_cli.py tests/test_runtime.py
PYTHONPATH=src pytest -q
```

Known passing evidence from the evolve pass:

- HOOO/gateway targeted: `36 passed`
- broader HOOO/CLI/runtime: `55 passed`
- full suite: `244 passed in 124.72s`

## Remaining backlog noted

These were not blockers for the local runtime correctness fix, but remain useful future hardening targets:

- Discord gateway live message-route for normal replies in HOOO threads, so `Other` freeform can be captured without manual CLI `hooo turn`.
- `render_mode: update_existing` still needs full gateway support; stale click rejection protects state correctness meanwhile.
- Per-run interaction handling should eventually use a lock or transactional recheck for concurrent same-revision clicks.
- Gateway callback should avoid falling back to card target IDs for observed-origin validation.
