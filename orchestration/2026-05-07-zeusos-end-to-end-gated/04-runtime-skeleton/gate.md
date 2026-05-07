# Stage 04 Gate — ZeusOS Runtime Deterministic Skeleton

**Stage:** `04-runtime-skeleton`  
**Mode:** additive runtime fixture implementation.  
**Allowed by:** Stages 00-03 PASS.

## Diff scope

- `src/jinwang_jarvis/zeus_os/worker.py`
  - Adds `run_deterministic_once()`.
  - Claims one `worker.<kind>` queue item.
  - Writes deterministic JSON evidence under registered task artifact root.
  - Registers artifact in SQLite.
  - Appends `worker.completed` event.
  - ACKs queue and completes work order.
- `src/jinwang_jarvis/zeus_os/cli.py`
  - `zeus worker run` now calls the deterministic fixture.
  - Unsupported worker kinds are rejected.
- `tests/test_zeus_worker.py`
  - No-work case.
  - One fake task/work_order/queue item processed exactly once.
  - CLI temp-workspace smoke test.

No schema migration was added; existing canonical schema/store/queue/events/artifacts are used.
No Hermes, gateway, systemd, wiki, Discord, browser, network, or external repo boundary was touched.

## Verification

```text
PYTHONPATH=src python -m pytest tests/test_zeus_worker.py tests/test_zeus_queue.py tests/test_zeus_cli.py -q
35 passed in 0.91s
```

## External/MoA review

External review result: **PASS — 97/100**.

Confirmed:
- SQLite schema/store/queue/worker fixture works in temp workspace.
- Deterministic worker processes exactly one fake task once.
- Queue transitions to `acked`; work order transitions to `completed`.
- Event log remains canonical via `task_events`.
- Artifact registry remains canonical via `artifacts` table + filesystem artifact.
- Projection offsets/A2A/Discord/Markdown are untouched.
- No stop-line violation.

Non-blocking note:
- `--once` is currently implicit because the deterministic skeleton always processes one item and exits. Future live worker promotion must make loop semantics explicit.

## Score

| Dimension | Weight | Score | Weighted |
|---|---:|---:|---:|
| Scope compliance | 25 | 100 | 25.00 |
| Canonical state discipline | 25 | 100 | 25.00 |
| Deterministic fixture behavior | 20 | 100 | 20.00 |
| Test/proof readiness | 15 | 98 | 14.70 |
| External/MoA alignment | 15 | 97 | 14.55 |

**FINAL_STAGE_04_GATE_SCORE: 99.25/100 — PASS.**

## Allowed next stage

Proceed to:

> **Stage 05 — Adapter manifest + browser recipe registry dry-run**

Only adapter/recipe declaration, validation, and dry-run/proposal artifacts are allowed. No external repo mutation, vendoring, live helper patch promotion, Hermes config change, or browser automation execution.
