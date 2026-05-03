---
name: houroboros
description: Jarvis-native Ouroboros loop skill for continuing Houroboros workflow runs, status, drift, and evolution.
metadata:
  category: software-development
  locale: ko-KR
---

# /houroboros — Jarvis-Native Ouroboros Loop

Use this skill when the user invokes `/houroboros`, asks to continue a Houroboros run, or asks for status/drift on a Jarvis workflow run.

The required workflow is Discord thread auto-open -> interactive Interview cards -> ambiguity gate -> Seed -> Execute/Claude Code handoff -> Evaluate -> Evolve with Status/Drift visibility. The interview can look like Deep Interview, but it is only the front-end requirement crystallization phase after the task-specific Discord operating thread exists or has a pending handoff. Always continue toward a locked seed, deterministic execution record or explicit Claude Code handoff, evaluation against acceptance criteria, and an evolution proposal when requested. `seed` is intentionally blocked until the interview ambiguity score is `<= 0.2`.

Required Discord interview UX: do not stop at a single "continue interview" button plus blank text instructions. For each unresolved dimension, generate **three concrete candidate answers** as button-selectable options plus an **Other / new opinion** path. After each selection or new opinion, update the structured interview state and present the next unresolved dimension/options. Freeform turns must not automatically reduce ambiguity; only structured labels, explicit UI choices, or clearly mapped "Other" input should resolve required dimensions.

Use the Jarvis CLI namespace:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros start --config config/pipeline.local.yaml --goal "..." --origin-platform discord --origin-channel-id "..." --origin-message-id "..." --auto-open-thread --thread-name "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros mark-thread-created --config config/pipeline.local.yaml --run-id "..." --thread-id "..." --jump-url "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros turn --config config/pipeline.local.yaml --run-id "..." --message "Scope: ..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros turn --config config/pipeline.local.yaml --run-id "..." --message "Acceptance: ..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros turn --config config/pipeline.local.yaml --run-id "..." --message "Constraint: ..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros turn --config config/pipeline.local.yaml --run-id "..." --message "Executor: claude-code"
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros turn --config config/pipeline.local.yaml --run-id "..." --message "Permission: seed approved"
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros seed --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros run --config config/pipeline.local.yaml --run-id "..." --executor claude-code
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros evaluate --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros evolve --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros status --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli houroboros export --config config/pipeline.local.yaml --run-id "..."
```

Discord thread context: use `--auto-open-thread` to request a task thread. New runs must always get a dedicated operating thread. If the command is invoked from an existing Discord thread, resolve the parent channel and create a new sibling thread under that parent; do not reuse/bind the current thread for the new run. Only reuse the current thread when explicitly continuing an existing `run_id`. Plain CLI writes a Jarvis-owned pending `discord.create_thread` handoff artifact rather than creating a real Discord thread; an injected adapter or Hermes/Boramae gateway can perform the live side effect explicitly and then call `mark-thread-created`. Continuing a flow should use `status` or `export` first, then append `turn` messages or advance the deterministic phase. In implementation, preserve the old thread as `source_origin_thread_id`, set `reuse_current_thread: false`, and keep executor handoffs deferred unless Jinwang explicitly asks to run a worker.

Hermes source remains untouched. This skill is a Jarvis-owned external skill contract; it must not require Hermes core changes, Hermes config rewrites, external API calls, or autonomous code execution. Deferred handoffs should be explicit and reviewable: require operator approval metadata, idempotency keys for repeat-safe consumption, strict validation for path-bearing IDs such as `run_id`, and secret redaction before writing user-originated goal/turn/card/handoff artifacts.
