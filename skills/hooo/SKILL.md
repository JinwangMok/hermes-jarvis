---
name: hooo
description: Jarvis Houroboros workflow harness for Discord-origin Interview -> Seed -> Execute -> Evaluate -> Evolve runs.
metadata:
  category: software-development
  locale: ko-KR
---

# /hooo — Jarvis Houroboros Workflow Harness

Use this skill when the user invokes `/hooo` or asks for an Ouroboros-style Jarvis workflow. Treat `/hooo` as a full workflow harness, not as interview-only UX.

Core flow: Discord thread auto-open -> interactive Interview cards -> ambiguity gate -> Seed -> Execute/Claude Code handoff -> Evaluate -> Evolve. Deep Interview-style questioning is only the requirement crystallization front end; the value is the task-specific operating thread, visible ambiguity score, unresolved decision list, spec-first seed, execution evidence, evaluation, drift visibility, and operator-controlled evolution loop.

The seed gate is mandatory: `seed` should fail while `interview_state.json` reports `ambiguity_score > 0.2`.

Required Discord interview UX: the user must not be forced into a blank "continue interview" form where they write every requirement from scratch. For each unresolved dimension (`Scope`, `Acceptance`, `Constraint`, `Executor`, `Permission`), HOOO should generate **three concrete selectable proposals** as Discord button choices plus an **Other / new opinion** path. The interview should proceed through multiple small selection/refinement steps: show options, let Jinwang choose by button or add a new natural-language opinion, update the structured state, then regenerate the next missing dimension/options. Natural-language fallback remains supported, but the default UX should be proposal-driven and button-selectable.

Continue the Discord interview by collecting `Scope:`, `Acceptance:`, `Constraint:`, `Executor:`, and `Permission:` turns or equivalent choices until the card reports `seed_ready: true`. Do not let arbitrary freeform text resolve all interview dimensions; freeform notes should remain notes unless they match a structured dimension or explicit UI choice.

Operate through the Jarvis CLI, not Hermes source. Prefer a dedicated Discord operating thread for every new `/hooo` run.

Discord thread rule is mandatory:
- If `/hooo` is invoked in a normal parent channel, start the run for that channel and let Hermes/Boramae auto-thread or create the task thread there.
- If `/hooo` is invoked from inside an existing Discord thread, do **not** bind the new run to the current thread. Treat the current thread only as the request origin, resolve its parent channel, create a new sibling thread under that parent, and bind the run to the new sibling thread.
- After creating the sibling thread, post the HOOO kickoff/status message into that new thread and tell the original thread to continue there.
- For Jarvis CLI state, use `--origin-channel-id <parent_channel_id>` and then record the new sibling thread via `mark-thread-created --thread-id <new_thread_id>`; do not pass the current thread as `--origin-thread-id` for a new run unless explicitly continuing an existing run.

In plain CLI mode this writes a safe pending `discord.create_thread` handoff artifact for Hermes/Boramae; when the real gateway creates the thread, mark it back into Jarvis:

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo start --config config/pipeline.local.yaml --goal "..." --origin-platform discord --origin-channel-id "..." --origin-message-id "..." --auto-open-thread --thread-name "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo mark-thread-created --config config/pipeline.local.yaml --run-id "..." --thread-id "..." --jump-url "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo turn --config config/pipeline.local.yaml --run-id "..." --message "Scope: ..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo turn --config config/pipeline.local.yaml --run-id "..." --message "Acceptance: ..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo turn --config config/pipeline.local.yaml --run-id "..." --message "Constraint: ..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo turn --config config/pipeline.local.yaml --run-id "..." --message "Executor: claude-code"
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo turn --config config/pipeline.local.yaml --run-id "..." --message "Permission: seed approved"
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo seed --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo run --config config/pipeline.local.yaml --run-id "..." --executor claude-code
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo evaluate --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo evolve --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo status --config config/pipeline.local.yaml --run-id "..."
```

Safety contract: do not modify Hermes source, `~/.hermes`, Hermes skills, wiki raw files, systemd, cron, secrets, or external services. The workflow writes Jarvis-owned state and artifacts under the configured workspace only. Seed v1 is immutable; evolution writes a proposal artifact instead of silently rewriting the seed. Deferred Discord/Claude handoffs must include `requires_explicit_operator_approval: true` and an idempotency key, validate path-bearing IDs such as `run_id`, and redact secret-like user input before artifact persistence.

Implementation pitfalls learned from the Discord-native redesign:
- Starting from an existing Discord thread with `--auto-open-thread` must create a sibling-thread handoff under the parent channel; keep the original thread only as `source_origin_thread_id` and set `reuse_current_thread: false`.
- Hermes `pre_gateway_dispatch` must return `{"action": "skip", "reason": ...}` after the plugin handles `/hooo`; returning legacy `{"skip": true}` does **not** stop normal parent-channel agent dispatch and causes duplicate threads plus real work running in the parent session.
- Claude Code/OpenCode executor integration should first write a deferred handoff artifact, not run the worker inline from `/hooo`.
- Deterministic placeholder execution/evaluation is dry-run evidence; expose warnings so it is not confused with real task completion.
- Live smoke should validate the real Discord sibling-thread side effect plus Jarvis card/reducer/seed path. If the tooling cannot impersonate a human Discord UI click, say so and treat `hooo interact --custom-id ...` as API-equivalent reducer validation, not as a physical UI click.
- Verification should include `compileall`, targeted HOOO/CLI regressions, full `pytest -q` with enough timeout for the Jarvis suite, and a CLI smoke that checks `interview_state.json`, `discord_cards.jsonl`, `thread_handoff.json`, `seed.json`, and `claude_code_handoff.json`.
- Proposal-driven interview state pitfall: after `Other / new opinion` sets `pending_freeform_dimension`, a later proposal selection for that same dimension must clear the pending marker while resolving only that dimension. Add regression coverage for `Other -> proposal` so status does not show stale pending freeform state after seed-ready.
- Final cleanup should split mixed workstreams into concern-based commits and then re-check gateway/config status without restarting. If a gateway/session reset interrupts closeout, resume from live git/remotes/tests/gateway state rather than the last chat summary; for Jarvis, verify both `origin` and `public` are pushed. See `references/live-smoke-and-cleanup.md` for the proven live-smoke, verification, post-restart continuation, and git-cleanup recipe.
