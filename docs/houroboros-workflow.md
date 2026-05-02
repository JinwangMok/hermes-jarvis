# Jarvis Houroboros Workflow

Houroboros is a Jarvis-native, Hermes-source-untouched workflow harness for turning a Discord-origin request into a task-specific operating thread, interactive interview state, immutable seed, explicit execution handoff, evaluation, drift visibility, and an evolution proposal.

The intended UX is now Discord-native, not CLI-only:

```text
/hooo <goal>
  -> reserve run row
  -> request/create dedicated sibling Discord thread
  -> post HOOO Interview card
  -> collect replies/choices as interview turns
  -> recompute ambiguity and publish unresolved decisions
  -> allow seed only when ambiguity <= 0.2
  -> create immutable Seed v1
  -> run deterministic dry-run or write Claude Code handoff
  -> evaluate evidence and write drift
  -> propose evolve without rewriting seed
```

## Interview state and cards

`start` writes `interview_state.json` and appends a `discord_cards.jsonl` card contract. This is a Jarvis-owned handoff format that a Hermes/Boramae gateway hook can render as a Discord interaction message with buttons such as `continue_interview`, `propose_seed`, and `cancel`.

The current deterministic ambiguity model tracks five required dimensions:

- `scope`
- `acceptance`
- `constraint`
- `executor`
- `permission`

Each `turn` updates `interview_state.json`, appends the raw message to `interview.jsonl`, and appends a new Discord card snapshot. Structured turns are recognized by prefixes such as `Scope:`, `Acceptance:`, `Constraint:`, `Executor:`, and `Permission:`. `seed` is blocked while `ambiguity_score > 0.2`.

## State and artifacts

Artifacts live under the configured Jarvis workspace:

- `state/houroboros.db`
- `data/houroboros/<run_id>/origin.json`
- `data/houroboros/<run_id>/thread_handoff.json` when thread creation is pending
- `data/houroboros/<run_id>/interview_state.json`
- `data/houroboros/<run_id>/discord_cards.jsonl`
- `data/houroboros/<run_id>/interview.jsonl`
- `data/houroboros/<run_id>/seed.json`
- `data/houroboros/<run_id>/seed.md`
- `data/houroboros/<run_id>/claude_code_handoff.json` when `run --executor claude-code` is selected
- `data/houroboros/<run_id>/execution_log.md`
- `data/houroboros/<run_id>/evaluation.md`
- `data/houroboros/<run_id>/drift.md`
- `data/houroboros/<run_id>/evolution.md`

Thread metadata is stored in `origin.json` and surfaced through `status`/`export`. When Hermes/Boramae finishes a pending handoff, record it with `houroboros mark-thread-created --run-id ... --thread-id ...`.

## Execution backend

Default `run` remains side-effect-free and writes deterministic dry-run evidence. `run --executor claude-code` does **not** launch Claude Code directly; it writes `claude_code_handoff.json` with a recommended `claude -p ... --max-turns ...` command and marks side effects as deferred. A separate explicitly authorized worker may consume that handoff.

`evaluation_mode=placeholder_substring_match` is intentionally labeled as a dry-run gate. A passing evaluation only means the recorded execution artifact contains the expected acceptance text; it is not proof of real-world task completion. `status` therefore emits a warning whenever deterministic-placeholder evidence reaches running/evaluated/evolved phases.

## Discord card contract

`discord_cards.jsonl` stores the render payload under `card.components`. Gateway renderers must read nested `card.components` and preserve `disabled` flags when constructing Discord buttons. Top-level `components` is a legacy fallback only; new renderers should not rely on it.

## Discord operating-thread rule

Every new `/hooo` run should own a dedicated task thread. If invoked in a parent channel, create/use a task thread under that channel. If invoked inside an existing Discord thread, derive the parent channel and create a new sibling thread under that parent; the existing thread is only the request origin. Only explicit continue/status/export for an existing `run_id` should reuse the current thread.

## Safety model

The harness writes only Jarvis-owned workspace files by default. It does not change Hermes source, `~/.hermes`, Hermes skills, wiki raw files, systemd units, cron jobs, secrets, or external services. Live Discord rendering and Claude Code execution remain explicit handoff surfaces.
