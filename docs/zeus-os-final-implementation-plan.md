# Zeus OS Final Implementation Plan

**Status:** final implementation contract after MoA review
**Date:** 2026-05-05
**Owner:** Jarvis / Zeus OS sidecar; Hermes remains upstream/source-untouched
**Supersedes:** `docs/plans/2026-05-05-zeus-os-replatform-implementation-plan.md` as the implementation contract. Supporting rationale remains in `docs/zeus-os-agent-runtime-design.md` and `docs/zeus-os-a2a-protocol-review.md`.

## 1. Executive decision

Reframe `jinwang-jarvis` as **Zeus OS**, a Jarvis-owned personal Agent OS/control plane. Hermes and Jarvis stay separated:

- **Hermes:** upstream runtime, gateway, tool execution environment, existing Discord connection.
- **Jarvis / Zeus OS:** local canonical multi-agent control plane, state, artifacts, orchestration, workers, approvals, projections, operator guides, and optional Discord/A2A adapters.

No Hermes core edits are allowed. Jarvis may provide Hermes plugins and sidecars.

## 2. Non-negotiable invariants

1. **Hermes source untouched.** Any integration lives in `jinwang-jarvis` modules/plugins/systemd templates.
2. **SQLite + artifacts are canonical.** Discord, A2A, markdown, and dashboards are projections.
3. **One Discord bot for MVP.** Personas are DB `agent_cards`, not separate bot accounts. Fake `@Agent` mentions are forbidden.
4. **A2A is compatibility/projection/edge transport.** It is not the internal source of truth or unbounded internal chat bus.
5. **Bounded collaboration only.** Every agent exchange is tied to `task_id`, agenda, max rounds, turn/budget limits, convergence condition, and final arbiter.
6. **Orchestrator does not execute side effects.** It decomposes, assigns, gates, and records.
7. **Workers do side effects only through approved adapters.** Risky operations require explicit approval.
8. **No secrets or private reasoning persistence.** Store summaries, evidence, assumptions, decisions, confidence, and artifact hashes only.
9. **Deterministic first.** Fake/stub workers and dry-run projections precede live LLM, Discord, A2A HTTP, OpenCode, or image-generation adapters.
10. **Paranoid verification.** Tests, static scans, independent review, doctor checks, artifact integrity, idempotency, and rollback/runbook checks precede commit/push.

## 3. Data layers

```text
Hot control plane: SQLite WAL
  tasks, work_orders, messages, approvals, decisions, task_events,
  leases, worker heartbeats, agent_cards, artifact metadata, projection_offsets

Artifact layer: filesystem
  data/zeus/tasks/<task_id>/<work_order_id>/...
  prompt/style/review/report/diff/image/log artifacts, registered by hash

Warm analytics: DuckDB / Parquet exports
  read-only reports over event/artifact metadata; never owns leases or task state

Cold archive later: Iceberg/object storage
  only after event volume/retention/multi-node analytics justify it
```

DuckDB and Iceberg must not replace SQLite for the hot runtime.

## 4. Canonical schema contract

Use `state/zeus_os.db`, SQLite WAL, `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, ISO-8601 UTC timestamps, JSON as TEXT, integer `revision` fields on mutable aggregate rows.

Required tables:

- `schema_migrations(version, name, applied_at)`
- `runtime_metadata(key, value_json, updated_at)`
- `agent_cards(agent_id, name, persona_type, description, version, capabilities_json, skills_json, protocols_json, registry_metadata_json, status, created_at, updated_at)`
- `worker_agents(worker_id, agent_id, kind, display_name, status, capabilities_json, current_work_order_id, heartbeat_at, lease_owner, metadata_json, created_at, updated_at)`
- `contexts(context_id, origin_platform, origin_channel_id, origin_thread_id, origin_message_id, user_id, title, status, metadata_json, created_at, updated_at)`
- `boardroom_sessions(session_id, context_id, task_id, title, status, max_rounds, current_round, final_arbiter_agent_id, budget_json, metadata_json, revision, created_at, updated_at, completed_at)`
- `boardroom_participants(session_id, agent_id, role, status, turn_budget_json, metadata_json, joined_at, updated_at)`
- `messages(message_id, context_id, task_id, role, sender_agent_id, parts_json, summary, visibility, metadata_json, extensions_json, reference_task_ids_json, idempotency_key, created_at)`
- `tasks(task_id, context_id, parent_task_id, title, user_goal, state, priority, assigned_orchestrator_id, current_worker_id, status_message, progress_percent, budget_json, result_summary, metadata_json, revision, created_at, updated_at, completed_at)`
- `agenda_items(agenda_item_id, session_id, task_id, title, state, turn_budget_json, convergence_condition, final_arbiter_agent_id, metadata_json, revision, created_at, updated_at)`
- `decisions(decision_id, task_id, session_id, title, decision_summary, rationale_summary, decided_by, state, scope_json, metadata_json, revision, created_at, updated_at)`
- `approvals(approval_id, task_id, work_order_id, gate_type, risk_class, scope_json, scope_hash, target_revision, state, requested_by, approved_by, expires_at, idempotency_key, metadata_json, created_at, updated_at)`
- `task_events(event_id, task_id, context_id, event_type, actor_type, actor_id, sequence, correlation_id, causation_id, idempotency_key, schema_version, payload_json, created_at)` with `UNIQUE(task_id, sequence)` and idempotency uniqueness where non-null.
- `work_orders(work_order_id, task_id, parent_work_order_id, worker_kind, capability_required, instruction_summary, instruction_path, state, lease_owner, lease_expires_at, heartbeat_at, attempt_count, max_attempts, result_summary, error_summary, metadata_json, revision, created_at, updated_at, completed_at)`
- `bus_queue(queue_id, topic, key, payload_json, state, lease_owner, lease_expires_at, attempt_count, max_attempts, available_at, idempotency_key, created_at, updated_at)` with `UNIQUE(topic, idempotency_key)` where non-null.
- `artifacts(artifact_id, task_id, work_order_id, name, description, kind, media_type, uri, visibility, sha256, size_bytes, provenance_json, metadata_json, created_by, created_at)`
- `projection_offsets(projection_name, task_id, last_event_sequence, status, error_summary, updated_at)`
- `dashboard_messages(dashboard_id, task_id, platform, channel_id, thread_id, message_id, revision, last_rendered_hash, last_event_sequence, last_rendered_at, created_at, updated_at)`

Seed default agents: `chair`, `pm`, `researcher`, `engineer`, `critic`, `scribe`, `qa`, `ops`, `security_auditor`, `cost_controller`, `memory_curator`, `painter`, `system`.

## 5. Canonical approval enum

DB `gate_type` must use one stable enum:

- `repo_write`
- `local_artifact_write`
- `external_post`
- `mail_calendar_write`
- `credential_access`
- `discord_config`
- `gateway_systemd`
- `cost_budget`
- `image_generation`
- `public_publication`
- `destructive_action`
- `human_input`

`risk_class` may refine the type, but cannot bypass `gate_type`.

Approval rules:

- approvals include `scope_json`, `scope_hash`, `target_revision`, `expires_at`, `idempotency_key`.
- stale revision/scope mismatch/expired approval is rejected.
- public publication is separate from image generation cost approval.
- Discord bot/gateway/systemd actions require explicit scoped human approval and rollback/runbook evidence.

## 6. Queue/work-order/event transaction contract

`bus_queue` is delivery. `work_orders` is canonical executable state.

Hard invariant:

1. State mutation + event append + queue enqueue happen in one `BEGIN IMMEDIATE` transaction.
2. Worker claim of `worker.<kind>` atomically leases both queue row and referenced `work_orders` row in one transaction.
3. Queue payload for worker topics includes `task_id`, `work_order_id`, `worker_kind`, expected work-order revision.
4. `renew`, `ack`, `nack`, `dead`, `cancel` require matching `lease_owner`; stale workers cannot ack after lease expiry/reclaim.
5. `ack/nack/dead/cancel` update queue row, work_order row, aggregate task/session state when applicable, and append a `task_events` row in one transaction.
6. Event sequence allocation is serialized by transaction helper; retry on `UNIQUE(task_id, sequence)` conflict if needed.
7. Expired recovery only touches `state='leased' AND lease_expires_at < now`.
8. Dead-letter is deterministic when `attempt_count >= max_attempts`.

Queue state machine:

```text
ready -> leased -> acked
ready -> leased -> ready(backoff)
ready -> leased -> dead
ready/leased -> canceled
```

Work order state machine:

```text
ready -> running -> completed
ready -> running -> retryable
ready/running -> failed
ready/running -> canceled
ready/running -> approval_required
```

## 7. Bounded A2A-like collaboration

A2A is exposed later, but bounded communication is internal from MVP.

Required enforcement:

- `boardroom_sessions.max_rounds`
- `boardroom_sessions.current_round`
- `boardroom_sessions.final_arbiter_agent_id`
- `agenda_items.turn_budget_json`
- `agenda_items.convergence_condition`
- `tasks.budget_json`
- event types: `round.started`, `round.closed`, `agent.activity`, `task.proposed`, `task.spawn_approved`, `task.spawn_rejected`, `approval.requested`, `approval.resolved`

Tests must prove:

- max rounds enforced.
- agenda turn budget enforced.
- agent-proposed spawned tasks require policy/user approval.
- final arbiter can close/escalate.
- no recursive unbounded agent chatter.

## 8. Artifact security contract

Add `artifacts.py` as a first-class module.

Required behavior:

- Artifact root is `data/zeus/tasks/<task_id>/` by default.
- Store logical/relative URIs; do not expose host absolute paths in normal Discord/A2A projection.
- Reject absolute paths, `..`, non-canonical paths, and symlink escapes.
- Write temp file, fsync/close, atomic rename, hash, size/MIME detect, then register metadata.
- Reconciliation checks detect missing files, hash mismatch, unregistered files, and registration without file.
- Generated images/logs/artifacts are not versioned unless intentionally added as docs fixtures.
- Redaction runs before DB message/artifact/log/projection/export persistence.

Tests:

- path traversal rejected.
- symlink escape rejected.
- hash mismatch detected.
- missing registered artifact detected.
- duplicate artifact idempotency handled.
- token-like values redacted from persisted artifacts and projections.

## 9. Redaction and persistence safety

Add `safety.py` or `redaction.py`.

Reject or redact:

- Discord bot tokens and bearer/API-key-like strings.
- private keys.
- `chain_of_thought`, `reasoning_trace`, raw hidden reasoning fields.
- local absolute paths in user-facing projection unless operator mode is explicitly requested.

Run safety checks on:

- messages
- artifacts
- logs
- Discord cards
- A2A projections
- analytics exports
- generated markdown guides/reports

## 10. CLI contract

Use one top-level Zeus subparser inside the existing Jarvis CLI. Implementation should delegate parser construction/execution to `src/jinwang_jarvis/zeus_os/cli.py`.

Canonical command vocabulary:

```bash
python -m jinwang_jarvis.cli zeus init
python -m jinwang_jarvis.cli zeus doctor
python -m jinwang_jarvis.cli zeus task submit --title ... --goal ...
python -m jinwang_jarvis.cli zeus task status <task_id> [--ops]
python -m jinwang_jarvis.cli zeus task replay <task_id>
python -m jinwang_jarvis.cli zeus task export <task_id>
python -m jinwang_jarvis.cli zeus agent list|show|add|enable|disable|retire
python -m jinwang_jarvis.cli zeus queue list|recover
python -m jinwang_jarvis.cli zeus worker list|drain
python -m jinwang_jarvis.cli zeus orchestrator --once
python -m jinwang_jarvis.cli zeus worker run --kind deterministic --once
```

Optional standalone `zeus` console script may come later.

## 11. Discord Boardroom UX contract

Thread is a **회의실 / boardroom**. Discord is a status/reporting surface.

Rules:

- Single real bot identity for MVP.
- Persona shown as structured prefix/card field, not fake mentions.
- Real mentions are reserved for Jinwang/human approval or attention.
- Normal mode hides raw DB IDs and host absolute paths.
- Operator mode may show IDs/paths via explicit `--ops` or operator command.

Card types:

1. **Session status card** — edited in place.
2. **Active agents card** — who is doing what now.
3. **Decision/approval card** — new message for important gates.
4. **Artifact/result card** — new message for outputs.
5. **Operator alert card** — dead letters, stale workers, projection drift.

Example normal status:

```text
[Zeus 회의실] <task title>
상태: 작업 중
현재 활동:
- PM: 요구사항과 acceptance 정리 중
- Researcher: 관련 문서 확인 중
- Painter: 시각화 brief 작성 중
다음 진왕님 액션: 없음
최근 산출물: brief.md, prompt.md
```

Approval card example:

```text
승인이 필요합니다: repo_write
작업: Zeus OS schema tests 추가
요청자: Engineer
범위:
- paths: src/jinwang_jarvis/zeus_os/*, tests/test_zeus_*.py
- commands: PYTHONPATH=src pytest -q tests/test_zeus_*.py
만료: <timestamp>
[이 범위 승인] [거절] [범위 줄여서 다시 요청]
```

Stale approval click response:

```text
이 승인 카드는 오래되었습니다. 최신 승인 요청을 아래에 다시 렌더링했습니다.
```

## 12. Active agent reporting

Activity projection is derived from `worker_agents`, `work_orders`, and `task_events`.

Minimum visible fields:

- agent id/display name/persona
- current task/work_order
- activity label
- phase/progress
- last heartbeat
- blocked reason
- next expected update

Tests must verify active, stale, blocked, completed, and failed activity rendering without private reasoning leakage.

## 13. Painter workflow

Painter is first-class and purpose-fit, not proposal-only.

Early deterministic Painter fixture should arrive before live image generation.

Flow:

1. PM/Chair fixes visual brief: purpose, audience, desired belief/understanding, medium/aspect ratio, claims, constraints, style, cost budget.
2. Painter writes `brief.md`, `prompt.md`, `style.md`, optional `composition.md`, and `review.md`.
3. `image_generation` adapter consumes approved prompt/style; live `gpt-image-2` is gated.
4. Worker registers `image.png`, variants, provenance, caption, alt text.
5. Critic/QA checks factual/safety/accessibility concerns.
6. Public publication requires separate approval.

## 14. A2A adapter contract

MVP: pure projection/mapping functions, no server required.

Mapping:

| Internal | A2A |
|---|---|
| `agent_cards` | AgentCard |
| `messages.parts_json` | Message.parts |
| `tasks.state` | TaskStatus.state |
| `artifacts` | Artifact.parts |
| `task_events` | future stream/subscribe events |

State mapping:

- `submitted` -> `TASK_STATE_SUBMITTED`
- `working` -> `TASK_STATE_WORKING`
- `completed` -> `TASK_STATE_COMPLETED`
- `failed` -> `TASK_STATE_FAILED`
- `canceled` -> `TASK_STATE_CANCELED`
- `input_required` -> `TASK_STATE_INPUT_REQUIRED`
- `rejected` -> `TASK_STATE_REJECTED`
- `auth_required` -> `TASK_STATE_AUTH_REQUIRED`

HTTP endpoints are future: `GET /agent-card`, `POST /message:send`, `GET /tasks/{id}`. SSE is deferred.

## 15. Implementation phases

### Phase A — docs and guide skeletons

Create/update:

- `docs/zeus-os-final-implementation-plan.md`
- `docs/zeus-os-usage-guide.md`
- `docs/zeus-os-operator-guide.md`

### Phase B — package/schema/store/safety/artifacts

Create:

- `src/jinwang_jarvis/zeus_os/__init__.py`
- `ids.py`, `schema.py`, `store.py`, `events.py`, `safety.py`, `artifacts.py`
- tests: `test_zeus_schema.py`, `test_zeus_events.py`, `test_zeus_safety.py`, `test_zeus_artifacts.py`

### Phase C — queue/work_order/CLI lifecycle

Create:

- `queue.py`, `cli.py`
- tests: `test_zeus_queue.py`, `test_zeus_cli.py`
- integrate nested `zeus` subparser in existing `src/jinwang_jarvis/cli.py`

### Phase D — orchestrator/deterministic worker/doctor

Create:

- `orchestrator.py`, `workers.py`, `doctor.py`
- tests: `test_zeus_orchestrator.py`, `test_zeus_workers.py`, `test_zeus_doctor.py`

### Phase E — approvals and bounded boardroom

Create:

- `approvals.py`, `boardroom.py`
- tests: `test_zeus_approvals.py`, `test_zeus_boardroom.py`

### Phase F — projection/Discord dry-run

Create:

- `projection.py`
- `plugins/hermes_zeus_gateway/__init__.py`
- `plugins/hermes_zeus_gateway/plugin.yaml`
- tests: `test_zeus_projection.py`, `test_zeus_gateway_plugin.py`
- golden snapshots: status, activity, approval, artifact cards

### Phase G — A2A mapping, Painter, fake image adapter, export

Create:

- `a2a.py`, `painter.py`, `image_generation.py`, `export.py`
- tests: `test_zeus_a2a.py`, `test_zeus_painter.py`, `test_zeus_image_generation.py`, `test_zeus_export.py`

### Phase H — ops templates and final guides

Create:

- `scripts/zeus-orchestrator.service.template`
- `scripts/zeus-worker.service.template`
- update guides.

Systemd templates must not be installed/enabled automatically.

## 16. Doctor requirements

`zeus doctor` must report:

- DB exists and schema version valid.
- WAL and foreign keys active.
- artifact root exists and is writable.
- artifact path escapes/hash mismatches/missing files.
- queue counts by topic/state.
- expired/stale leases.
- stale worker heartbeats.
- dead letters.
- pending/stale approvals.
- projection lag/offsets.
- secret-like persisted values in messages/artifacts/projections.
- config paths rooted under approved workspace.

## 17. Verification gates

Targeted tests:

```bash
PYTHONPATH=src pytest -q tests/test_zeus_*.py
```

Full feasible suite:

```bash
PYTHONPATH=src pytest -q
python -m compileall -q src/jinwang_jarvis tests
```

Security checks:

- scan staged and untracked files.
- prefer `gitleaks` or `detect-secrets` if available.
- fallback grep for token/password/API key/private key patterns.
- scan `data/zeus` artifacts and generated docs.

Independent review before commit:

- architecture/runtime
- security/ops
- product/UX
- final diff review after fixes

## 18. Discord bot/token handoff gate

Stop and ask Jinwang for bot/app/token only after:

1. CLI-only deterministic Zeus OS passes tests.
2. Discord plugin dry-run tests pass without gateway restart.
3. operator guide lists exact scopes/permissions.
4. no secrets are in repo/artifacts.

Request must not ask for token in chat. Ask Jinwang to place it in an agreed secret file outside repo with `0600` permissions.

Minimum permissions: send messages, read message history, create public threads, use slash commands/components. Manage webhooks is optional later. Avoid Administrator.

## 19. Gateway/systemd live action gate

Before any live gateway/systemd action:

- verify Jarvis-owned Hermes gateway recovery arm is present.
- capture service status and current unit/env.
- document rollback command.
- require scoped human approval.
- perform health/smoke after action.

No gateway restart is part of the initial code implementation unless Jinwang explicitly approves that live step.

## 20. Commit/push policy

Before commit:

- `git status --short`
- review untracked/generated artifacts.
- targeted tests pass.
- full feasible suite passes or unrelated live-tool failures are proven baseline.
- compileall passes.
- secret scan passes.
- independent review passes.
- usage/operator guide updated.

Commit message candidate:

```bash
git commit -m "feat: add Zeus OS control-plane foundation"
```

Push after final local verification and explicit scope remains the current task’s requested scope.
