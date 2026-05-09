---
name: minerva
description: ZeusOS Minerva workflow harness for Discord-origin Interview -> Seed -> Execute -> Evaluate -> Evolve runs.
metadata:
  category: software-development
  locale: ko-KR
---

# /minerva — ZeusOS Minerva Workflow Harness

Use this skill when the user invokes `/minerva` or asks for an Ouroboros-style ZeusOS workflow. Treat `/minerva` as a full workflow harness, not as interview-only UX.

Core flow: Discord thread auto-open -> interactive Interview cards -> ambiguity gate -> Seed -> Execute/Claude Code handoff -> Evaluate -> Evolve. Deep Interview-style questioning is only the requirement crystallization front end; the value is the task-specific operating thread, visible ambiguity score, unresolved decision list, spec-first seed, execution evidence, evaluation, drift visibility, and operator-controlled evolution loop.

Minerva directional-control rule: every user turn must create a self-alignment checkpoint before the next action is treated as valid. The checkpoint records the latest user instruction, the active run goal, the question “does the next action still serve the instruction and goal?”, the chosen next step, unresolved dimensions, and live-boundary caution. This is not optional narration; it is runtime state so Minerva/Minerva cannot drift into a nearby but wrong task.

Process-gate model pointer: the pure, reusable canonical Minerva phase/gate data model lives in `src/zeus_os/minerva_process.py`; Minerva seed metadata may reference it as `minerva_process_gate`, and the read-only CLI should expose `minerva-process-contract` / `minerva-phase-gate` for deterministic threshold inspection. Minerva `seed` should materialize `workflow_design.json`, and `run()` should consume that artifact and block when its gate fails. This remains repo/test/temp-workspace gating unless a separate live Hermes/gateway wiring gate is approved. For the role split and full phase loop, see `references/minerva-process-gate-architecture-2026-05-09.md`.

Scope-correction rule: when Minerva/Minerva is being used inside ZeusOS repository rearchitecture, the scope is the whole ZeusOS Agent OS platform unless Jinwang explicitly narrows it. Do not mistake Minerva itself, Mail Secretary, gateway recovery, or any other useful leaf for the main mission. Treat each as a leaf under the original target: a template-based, extensible, declarative ZeusOS. Before every next step, realign to the original instruction, the latest correction, and the safest next repo-wide leaf. See `references/minerva-zeusos-scope-correction-2026-05-09.md`.

The seed gate is mandatory: `seed` should fail while `interview_state.json` reports `ambiguity_score > 0.2` **or any required interview dimension remains unresolved**. Do not treat the numeric threshold alone as sufficient; with five dimensions, `ambiguity_score == 0.2` can still mean one critical dimension such as `Permission` is missing.

Required Discord interview UX: the user must not be forced into a blank "continue interview" form where they write every requirement from scratch. For each unresolved dimension (`Scope`, `Acceptance`, `Constraint`, `Executor`, `Permission`), Minerva should generate **three concrete selectable proposals** as Discord button choices plus an **Other / new opinion** path. The interview should proceed through multiple small selection/refinement steps: show options, let Jinwang choose by button or add a new natural-language opinion, update the structured state, then regenerate the next missing dimension/options. Natural-language fallback remains supported, but the default UX should be proposal-driven and button-selectable.

Continue the Discord interview by collecting `Scope:`, `Acceptance:`, `Constraint:`, `Executor:`, and `Permission:` turns or equivalent choices until the card reports `seed_ready: true`. Do not let arbitrary freeform text resolve all interview dimensions; freeform notes should remain notes unless they match a structured dimension or explicit UI choice.

When Jinwang asks to "다시 인터뷰 방식으로" judge the current state, do not jump straight to implementation. First answer in the five interview dimensions, then present concrete choices. If he asks to set `Acceptance` aggressively, upgrade it into a defensible target state and create/revise a review-gated implementation plan before coding: separate final acceptance from next-phase exit criteria, require a real runtime caller before claiming operational migration, add guardrails, exact RED/GREEN commands, independent reviewer lenses, and rollback/no-op rollback notes.

Legibility rule for ZeusOS/Minerva progress reports: start with an easy Korean one-line explanation or analogy before commit hashes, test counts, or implementation details. Jinwang may ask "알아듣게 설명해" when the report is too implementation-heavy; future reports should proactively explain the meaning of each leaf in plain terms (e.g. "지도와 출입 규칙", "도구가 그 지도를 보기 시작함", "registry를 안전하게 읽는 목록 API") and only then give RED/GREEN/review/commit evidence. After each leaf, continue the interview loop by offering 2-3 concrete next choices with one recommended option and a short reason.

Plain-language reporting rule: after executing a Minerva/ZeusOS leaf, explain it first in understandable terms before commit/test minutiae. Use a one-line "what changed" plus a concrete analogy if helpful (for example, path policy as a map/access rule), then evidence. If Jinwang says "알아듣게 설명해", treat that as a style correction: reduce jargon, explain why the change matters operationally, and only then list commits/tests. Continue the interview by offering the next `A/B/C` choices with a recommendation and risk note, not by dumping implementation details.

Operate through the ZeusOS CLI, not Hermes source. Prefer a dedicated Discord operating thread for every new `/minerva` run.

Discord thread rule is mandatory:
- If `/minerva` is invoked in a normal parent channel, start the run for that channel and let Hermes/Boramae auto-thread or create the task thread there.
- If `/minerva` is invoked from inside an existing Discord thread, do **not** bind the new run to the current thread. Treat the current thread only as the request origin, resolve its parent channel, create a new sibling thread under that parent, and bind the run to the new sibling thread.
- After creating the sibling thread, post the Minerva kickoff/status message into that new thread and tell the original thread to continue there.
- For ZeusOS CLI state, use `--origin-channel-id <parent_channel_id>` and then record the new sibling thread via `mark-thread-created --thread-id <new_thread_id>`; do not pass the current thread as `--origin-thread-id` for a new run unless explicitly continuing an existing run.

In plain CLI mode this writes a safe pending `discord.create_thread` handoff artifact for Hermes/Boramae; when the real gateway creates the thread, mark it back into ZeusOS:

```bash
PYTHONPATH=src python3 -m zeus_os.cli minerva start --config config/pipeline.local.yaml --goal "..." --origin-platform discord --origin-channel-id "..." --origin-message-id "..." --auto-open-thread --thread-name "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva mark-thread-created --config config/pipeline.local.yaml --run-id "..." --thread-id "..." --jump-url "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Scope: ..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Acceptance: ..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Constraint: ..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Executor: claude-code"
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Permission: seed approved"
PYTHONPATH=src python3 -m zeus_os.cli minerva seed --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva run --config config/pipeline.local.yaml --run-id "..." --executor claude-code
PYTHONPATH=src python3 -m zeus_os.cli minerva evaluate --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva evolve --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva status --config config/pipeline.local.yaml --run-id "..."
```

Safety contract: do not modify Hermes source, `~/.hermes`, Hermes skills, wiki raw files, systemd, cron, secrets, or external services. The workflow writes ZeusOS-owned state and artifacts under the configured workspace only. Seed v1 is immutable; evolution writes a proposal artifact instead of silently rewriting the seed. Deferred Discord/Claude handoffs must include `requires_explicit_operator_approval: true` and an idempotency key, validate path-bearing IDs such as `run_id`, and redact secret-like user input before artifact persistence.

Implementation pitfalls learned from the Discord-native redesign:
- Starting from an existing Discord thread with `--auto-open-thread` must create a sibling-thread handoff under the parent channel; keep the original thread only as `source_origin_thread_id` and set `reuse_current_thread: false`.
- Hermes `pre_gateway_dispatch` must return `{"action": "skip", "reason": ...}` after the plugin handles `/minerva`; returning legacy `{"skip": true}` does **not** stop normal parent-channel agent dispatch and causes duplicate threads plus real work running in the parent session.
- Claude Code/OpenCode executor integration should first write a deferred handoff artifact, not run the worker inline from `/minerva`.
- Deterministic placeholder execution/evaluation is dry-run evidence; expose warnings so it is not confused with real task completion.
- Live smoke should validate the real Discord sibling-thread side effect plus ZeusOS card/reducer/seed path. If the tooling cannot impersonate a human Discord UI click, say so and treat `minerva interact --custom-id ...` as API-equivalent reducer validation, not as a physical UI click.
- Verification should include `compileall`, targeted Minerva/CLI regressions, full `pytest -q` with enough timeout for the ZeusOS suite, and a CLI smoke that checks `interview_state.json`, `discord_cards.jsonl`, `thread_handoff.json`, `seed.json`, and `claude_code_handoff.json`.
- Proposal-driven interview state pitfall: after `Other / new opinion` sets `pending_freeform_dimension`, a later proposal selection for that same dimension must clear the pending marker while resolving only that dimension. A plain natural-language reply immediately after `Other` should also resolve **only the pending dimension** (not become a generic note and not resolve all dimensions). Add regression coverage for both `Other -> proposal` and `Other -> plain freeform reply` so status does not show stale pending freeform state and seed remains blocked until all required dimensions are resolved.
- Seed-readiness pitfall: compute `seed_ready` as `not unresolved and ambiguity_score <= threshold`; never as threshold-only. Add a regression for the 4/5 resolved case where `ambiguity_score == 0.2` but `permission` or another dimension remains unresolved. `seed()` should reject it with an error naming the unresolved dimension(s). See `references/proposal-ux-evolve-hardening-2026-05-03.md` for the concrete fix and verification record.
- Final cleanup should split mixed workstreams into concern-based commits and then re-check gateway/config status without restarting. If a gateway/session reset interrupts closeout, resume from live git/remotes/tests/gateway state rather than the last chat summary; for ZeusOS, verify both `origin` and `public` are pushed. See `references/live-smoke-and-cleanup.md` for the proven live-smoke, verification, post-restart continuation, and git-cleanup recipe.
- ZeusOS repository rearchitecture leaves should follow the safe sequence captured in `references/zeusos-rearchitecture-leaf-pattern-2026-05-08.md`: explain plainly first, TDD each leaf, preserve old API behavior while adding optional policy/registry paths, stage only the leaf files, scan/review before commit, and avoid claiming runtime migration until a real ZeusOS-owned caller consumes registry metadata with fallback. For manifest-driven compatibility bridges, validate all path-like metadata such as `legacyName` as a single relative name before any caller joins it to roots; independent review already caught `../credentials` traversal risk in the Minerva/Minerva bridge leaf. When adding a second read-only caller such as skill search/index, preserve old falsy API behavior like `skill_roots=[]` default-root fallback and add a regression test before committing.
- For declaration-only script classification leaves, use `references/zeusos-script-classification-manifests-2026-05-08.md`: add `legacyScripts` metadata to capability manifests, validate script paths as repo-relative `scripts/...` only, require `migration: classify-only`, and do not move scripts or change cron/systemd/gateway/runtime wiring.
- For ZeusOS pre-merge gates and chained choices like `C->A`, use `references/zeusos-premerge-and-repository-ops-classification-2026-05-08.md`: commit the review/checklist gate first, then the next declarative leaf; keep docs-only scan commands from self-triggering staged secret regexes by pointing to the review skill instead of embedding full grep patterns; classify tracked repository ops scripts separately from safety-critical gateway recovery scripts and untracked mail/runtime work.
- For Minerva/Minerva directional scope corrections during ZeusOS rearchitecture, use `references/minerva-zeusos-scope-correction-2026-05-09.md`: the mission remains the whole ZeusOS Agent OS platform unless Jinwang explicitly narrows it; every leaf should realign to that mission before implementation.


<!-- merged from skills/minerva/SKILL.md -->

---
name: minerva
description: ZeusOS-native Ouroboros loop skill for continuing Minerva workflow runs, status, drift, and evolution.
metadata:
  category: software-development
  locale: ko-KR
---

# /minerva — ZeusOS-Native Ouroboros Loop

Use this skill when the user invokes `/minerva`, asks to continue a Minerva run, or asks for status/drift on a ZeusOS workflow run.

The required workflow is Discord thread auto-open -> interactive Interview cards -> ambiguity gate -> Seed -> Execute/Claude Code handoff -> Evaluate -> Evolve with Status/Drift visibility. The interview can look like Deep Interview, but it is only the front-end requirement crystallization phase after the task-specific Discord operating thread exists or has a pending handoff. Always continue toward a locked seed, deterministic execution record or explicit Claude Code handoff, evaluation against acceptance criteria, and an evolution proposal when requested. `seed` is intentionally blocked until the interview ambiguity score is `<= 0.2`.

Required Discord interview UX: do not stop at a single "continue interview" button plus blank text instructions. For each unresolved dimension, generate **three concrete candidate answers** as button-selectable options plus an **Other / new opinion** path. After each selection or new opinion, update the structured interview state and present the next unresolved dimension/options. Freeform turns must not automatically reduce ambiguity; only structured labels, explicit UI choices, or clearly mapped "Other" input should resolve required dimensions.

Use the ZeusOS CLI namespace:

```bash
PYTHONPATH=src python3 -m zeus_os.cli minerva start --config config/pipeline.local.yaml --goal "..." --origin-platform discord --origin-channel-id "..." --origin-message-id "..." --auto-open-thread --thread-name "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva mark-thread-created --config config/pipeline.local.yaml --run-id "..." --thread-id "..." --jump-url "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Scope: ..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Acceptance: ..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Constraint: ..."
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Executor: claude-code"
PYTHONPATH=src python3 -m zeus_os.cli minerva turn --config config/pipeline.local.yaml --run-id "..." --message "Permission: seed approved"
PYTHONPATH=src python3 -m zeus_os.cli minerva seed --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva run --config config/pipeline.local.yaml --run-id "..." --executor claude-code
PYTHONPATH=src python3 -m zeus_os.cli minerva evaluate --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva evolve --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva status --config config/pipeline.local.yaml --run-id "..."
PYTHONPATH=src python3 -m zeus_os.cli minerva export --config config/pipeline.local.yaml --run-id "..."
```

Discord thread context: use `--auto-open-thread` to request a task thread. New runs must always get a dedicated operating thread. If the command is invoked from an existing Discord thread, resolve the parent channel and create a new sibling thread under that parent; do not reuse/bind the current thread for the new run. Only reuse the current thread when explicitly continuing an existing `run_id`. Plain CLI writes a ZeusOS-owned pending `discord.create_thread` handoff artifact rather than creating a real Discord thread; an injected adapter or Hermes/Boramae gateway can perform the live side effect explicitly and then call `mark-thread-created`. Continuing a flow should use `status` or `export` first, then append `turn` messages or advance the deterministic phase. In implementation, preserve the old thread as `source_origin_thread_id`, set `reuse_current_thread: false`, and keep executor handoffs deferred unless Jinwang explicitly asks to run a worker.

Hermes source remains untouched. This skill is a ZeusOS-owned external skill contract; it must not require Hermes core changes, Hermes config rewrites, external API calls, or autonomous code execution. Deferred handoffs should be explicit and reviewable: require operator approval metadata, idempotency keys for repeat-safe consumption, strict validation for path-bearing IDs such as `run_id`, and secret redaction before writing user-originated goal/turn/card/handoff artifacts.
