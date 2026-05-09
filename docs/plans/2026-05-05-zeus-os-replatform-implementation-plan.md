# Zeus OS Replatform Implementation Plan

> **For Hermes/Boramae:** Use `subagent-driven-development` or the Jinwang OpenCode tmux team pattern to implement this plan task-by-task. Keep Hermes source untouched. ZeusOS is expanded into Zeus OS as a ZeusOS-owned sidecar/control-plane runtime.

**Goal:** Reframe `zeus-os` as the durable Zeus OS control plane while keeping Hermes as the upstream runtime/gateway/tool host, then implement a verifiable multi-agent boardroom runtime with DB-backed personas, A2A-compatible messaging, Discord reporting, Painter visual workflows, and paranoid verification.

**Architecture:** Hermes remains the always-on agent/gateway integration surface. ZeusOS becomes Zeus OS: the local canonical control plane with SQLite WAL, filesystem artifacts, typed events, queue leases, agent cards, worker adapters, approval gates, and Discord/A2A projections. Discord is a boardroom/reporting UX, not the source of truth.

**Tech Stack:** Python package in `src/zeus_os`, SQLite WAL, filesystem artifacts under `data/zeus`, pytest, existing ZeusOS CLI/plugin patterns, optional OpenCode/tmux worker, optional Hermes subprocess worker, future thin A2A HTTP adapter, future DuckDB/Parquet analytics export.

---

## 0. Non-negotiable boundaries

1. **Hermes and ZeusOS remain separated.** Hermes core is not modified. ZeusOS/ZeusOS owns plugins, sidecars, state, skills, docs, and systemd templates.
2. **ZeusOS is expanded into Zeus OS, not replaced abruptly.** Existing mail/calendar/hot-issue/Minerva features remain valid ZeusOS lanes under the broader Zeus OS control-plane model.
3. **Canonical state is DB + artifacts.** Discord/webhook/persona messages are projections only.
4. **One Discord app/bot for MVP.** Personas are `agent_cards`, not separate bot accounts. Named webhooks may be added later only as rendering projection.
5. **A2A is compatibility/projection/edge transport, not the internal source of truth.** Internal coordination remains typed durable tasks/events/work_orders.
6. **No unbounded agent chatter.** Every agent-to-agent interaction needs `task_id`, agenda, max rounds, budget, convergence condition, and final arbiter.
7. **Risky side effects require approval.** Gateway/systemd, repo mutation, external posting, mail/calendar writes, credential use, public image publication, and high-cost generation require explicit human approval.
8. **No private chain-of-thought persistence.** Store summaries, evidence, assumptions, decisions, artifacts, and confidence only.
9. **Deterministic first.** Every core flow ships with fake/stub workers and tests before live LLM/tool adapters.
10. **Paranoid verification before commit/push.** Targeted tests, full suite when feasible, static scans, independent review, artifact/path/secret checks, and live-smoke only behind approval.

## 1. Target mental model

```text
Hermes Agent
  - upstream runtime/gateway/tool execution environment
  - receives Discord messages and can load ZeusOS-owned plugins
  - remains source-untouched

ZeusOS -> Zeus OS
  - local personal Agent OS/control plane
  - owns state/zeus_os.db
  - owns data/zeus/tasks/<task_id>/ artifacts
  - owns orchestrator/worker daemons
  - owns capability registry/persona cards
  - owns approval/risk policy
  - exposes CLI, Discord projection, and later A2A HTTP adapter
```

## 2. Data-layer decision

Use a three-temperature hierarchy:

```text
Hot: SQLite WAL control plane
  tasks, work_orders, messages, approvals, decisions, task_events,
  leases, worker heartbeat, artifact metadata, projection offsets

Blob/artifact layer: filesystem
  prompts, logs, reports, diffs, generated images, reviews, handoffs

Warm: DuckDB/Parquet analytics export
  latency, retries, worker utilization, approval bottlenecks, cost/token trends

Cold later: Iceberg/Object store
  only when long-retention or multi-machine analytics requires it
```

Do **not** replace SQLite with DuckDB/Iceberg for the hot layer. They are downstream analytical layers, not runtime lease/queue/approval stores.

## 3. A2A decision

A2A is added as a contract boundary, not as the internal bus:

```text
Discord / CLI / A2A HTTP adapter
  -> validate + normalize input
  -> write canonical DB rows
  -> orchestrator claims/decomposes bounded work
  -> workers produce events/artifacts
  -> projection exposes A2A-shaped AgentCard/Task/Message/Artifact views
```

Mapping:

| Zeus OS internal | A2A-facing concept |
|---|---|
| `agent_cards` | AgentCard |
| `messages.parts_json` | Message.parts |
| `tasks.state` | TaskStatus.state |
| `artifacts` + files | Artifact.parts |
| `task_events` | stream/subscribe events later |

MVP implements schema compatibility first. HTTP endpoints come later: `GET /agent-card`, `POST /message:send`, `GET /tasks/{id}`. SSE/streaming is deferred.

## 4. Persona/capability registry

Personas are data records:

- `chair`: final arbiter / user-facing controller
- `pm`: decomposition, acceptance criteria, budget/round limits
- `researcher`: repo/wiki/web/document research
- `engineer`: implementation proposal and code work orders
- `critic`: risk, missing-question, contradiction review
- `scribe`: minutes, decisions, artifact index, user-facing guide
- `qa`: tests, regression gates, acceptance evidence
- `ops`: systemd/gateway/cron/queue recovery with approvals
- `security_auditor`: secrets, permissions, prompt-injection/path-traversal review
- `cost_controller`: token/time/image-generation budgets
- `memory_curator`: wiki/memory promotion and forgetting proposals
- `painter`: purpose-fit visual/diagram/image synthesis

Capability matching must be dynamic: add/disable/version/evaluate agent cards without hardcoding today’s roster as final truth.

## 5. Painter workflow

Painter is not proposal-only. It creates purpose-fit visual artifacts for whatever task needs visual communication.

Flow:

1. PM/Chair fixes or infers visual brief: purpose, audience, what the image must make the reader believe/understand, medium/aspect ratio, factual constraints, style, cost budget.
2. Painter/OpenCode design worker writes:
   - `brief.md`
   - `prompt.md`
   - `style.md`
   - optional `composition.md`
   - `review.md`
3. `image_generation` worker calls `gpt-image-2` only through a gated adapter.
4. Worker writes `image.png`, `variants/`, metadata/provenance.
5. Painter performs visual QA; Critic/QA checks factual/safety/accessibility issues.
6. Scribe records selected image, caption, alt text, and limitations.

## 6. Implementation phases and tasks

### Phase 1 — Final design/docs consolidation

**Objective:** Produce one canonical implementation contract before coding.

**Files:**
- Create/modify: `docs/zeus-os-final-implementation-plan.md`
- Keep supporting docs: `docs/zeus-os-agent-runtime-design.md`, `docs/zeus-os-a2a-protocol-review.md`

**Tasks:**
1. Consolidate this plan, runtime design, A2A review, and Painter/data-layer decisions into one final doc.
2. Run MoA review with at least four lenses: architecture, backend/runtime, security/ops, UX/product.
3. Patch final doc with consensus-worthy findings.
4. Mark deferred/future items explicitly.

**Acceptance:** final doc is internally consistent, implementable in phases, and names exact files/tests/commands.

### Phase 2 — Package skeleton and schema bootstrap

**Objective:** Add Zeus OS module skeleton and SQLite migration/bootstrap.

**Files:**
- Create: `src/zeus_os/zeus_os/__init__.py`
- Create: `src/zeus_os/zeus_os/ids.py`
- Create: `src/zeus_os/zeus_os/schema.py`
- Create: `src/zeus_os/zeus_os/store.py`
- Create: `tests/test_zeus_schema.py`

**Implementation:**
- `bootstrap(db_path)` creates tables and PRAGMAs.
- Use `state/zeus_os.db` default but tests use temp DB.
- Tables: `schema_migrations`, `runtime_metadata`, `agent_cards`, `worker_agents`, `contexts`, `boardroom_sessions`, `boardroom_participants`, `messages`, `tasks`, `agenda_items`, `decisions`, `approvals`, `task_events`, `work_orders`, `bus_queue`, `artifacts`, `dashboard_messages`.
- Seed default agent cards including `painter`.

**Tests:**
- PRAGMAs applied.
- all tables/indexes exist.
- FK enforcement works.
- default agent cards contain required roles/capabilities.

### Phase 3 — IDs, events, queue, and lease semantics

**Objective:** Implement durable queue/event primitives.

**Files:**
- Create: `src/zeus_os/zeus_os/events.py`
- Create: `src/zeus_os/zeus_os/queue.py`
- Create: `tests/test_zeus_events.py`
- Create: `tests/test_zeus_queue.py`

**Implementation:**
- deterministic safe ID helpers with path-traversal rejection.
- append-only task events with per-task sequence.
- `enqueue`, `claim_ready`, `renew`, `ack`, `nack`, `recover_expired`.
- atomic claim via `BEGIN IMMEDIATE` and lease expiry predicate.
- retries with max attempts and dead-letter state.

**Tests:**
- concurrent claim cannot double-claim.
- expired lease can be recovered.
- ack/nack append events.
- invalid IDs rejected.

### Phase 4 — CLI-only lifecycle

**Objective:** Allow Zeus OS to run without Discord or live agents.

**Files:**
- Create: `src/zeus_os/zeus_os/cli.py`
- Modify: `src/zeus_os/cli.py`
- Create: `tests/test_zeus_cli.py`

**Commands:**
- `zeus init`
- `zeus agent list`
- `zeus agent add/disable/enable`
- `zeus task submit`
- `zeus task status`
- `zeus queue list`
- `zeus doctor`

**Tests:**
- CLI creates DB.
- submitting a task creates context/task/message/event/queue rows.
- agent registry commands work.
- doctor reports missing/live-safe states without side effects.

### Phase 5 — Orchestrator and deterministic worker

**Objective:** Implement core boardroom mechanics without LLMs.

**Files:**
- Create: `src/zeus_os/zeus_os/orchestrator.py`
- Create: `src/zeus_os/zeus_os/workers.py`
- Create: `tests/test_zeus_orchestrator.py`
- Create: `tests/test_zeus_workers.py`

**Implementation:**
- Orchestrator `--once` claims `orchestrator.inbox`.
- Creates bounded agenda and one or more work orders.
- Deterministic worker claims `worker.deterministic` and writes report artifact.
- Artifact registration hashes files and stores metadata.

**Tests:**
- orchestrator never performs external side effects.
- worker artifacts are registered with hashes.
- task reaches completed/failed deterministically.

### Phase 6 — Approval/risk gates

**Objective:** Prevent unsafe work before live adapters.

**Files:**
- Create: `src/zeus_os/zeus_os/approvals.py`
- Create: `tests/test_zeus_approvals.py`

**Implementation:**
- risk classes: read_only, local_artifact_write, repo_write, external_post, mail_calendar_write, gateway_systemd, credential_access, image_generation_cost, public_publication.
- approval records include scope, revision, expiry, approver, and idempotency key.
- stale approval rejected after scope/revision changes.

**Tests:**
- risky work_order blocked without approval.
- approval scope mismatch rejected.
- expired/stale approval rejected.

### Phase 7 — Projection and Discord boardroom dry-run

**Objective:** Render boardroom state from DB/events.

**Files:**
- Create: `src/zeus_os/zeus_os/projection.py`
- Create: `plugins/hermes_zeus_gateway/__init__.py`
- Create: `tests/test_zeus_projection.py`
- Create: `tests/test_zeus_gateway_plugin.py`

**Implementation:**
- render markdown/cards from DB state.
- plugin is enqueue-only and render-only.
- no gateway restart in tests.
- one bot/persona projection; optional webhook adapter remains future.

**Tests:**
- projection rebuilds from event log.
- plugin creates DB task from Discord command.
- stale buttons/idempotency rejected.

### Phase 8 — A2A-compatible adapter scaffold

**Objective:** Add real under-the-hood A2A boundary without making A2A canonical.

**Files:**
- Create: `src/zeus_os/zeus_os/a2a.py`
- Create: `tests/test_zeus_a2a.py`

**Implementation:**
- JSON serialization for AgentCard, Message, Task, TaskStatus, Artifact.
- DB-to-A2A projection functions.
- `message_send_to_task()` normalization function.
- HTTP server optional/future; keep MVP adapter pure/testable.

**Tests:**
- default `agent_cards` project to AgentCard JSON.
- submitted/completed/failed/input_required states map correctly.
- artifacts map with URI/hash/provenance.

### Phase 9 — Painter and image-generation adapter scaffold

**Objective:** Support purpose-fit image workflows safely.

**Files:**
- Create: `src/zeus_os/zeus_os/painter.py`
- Create: `src/zeus_os/zeus_os/image_generation.py`
- Create: `tests/test_zeus_painter.py`
- Create: `tests/test_zeus_image_generation.py`

**Implementation:**
- Painter fixture worker writes `brief.md`, `prompt.md`, `style.md`, `review.md`.
- fake image adapter writes deterministic metadata/image placeholder artifact.
- live `gpt-image-2` adapter remains behind explicit approval and config availability.

**Tests:**
- Painter selected when task requests image/diagram/visual artifact.
- image generation blocked without cost/safety approval.
- prompt/style provenance registered.

### Phase 10 — Warm analytics export

**Objective:** Prepare DuckDB/Parquet reporting without making it runtime-critical.

**Files:**
- Create: `src/zeus_os/zeus_os/export.py`
- Create: `tests/test_zeus_export.py`

**Implementation:**
- export events/artifact metadata to JSONL initially; Parquet if dependency exists.
- DuckDB query examples in docs.
- no Iceberg implementation in MVP.

**Tests:**
- export contains stable schema/version.
- exported rows match event log count.

### Phase 11 — Ops/systemd templates and guide

**Objective:** Provide operator path without enabling live always-on services prematurely.

**Files:**
- Create: `scripts/zeus-orchestrator.service.template`
- Create: `scripts/zeus-worker.service.template`
- Create: `docs/zeus-os-usage-guide.md`
- Create: `docs/zeus-os-operator-guide.md`

**Implementation:**
- templates only; do not install/enable services automatically.
- guide explains CLI-only, Discord dry-run, approval gates, Painter, A2A projection.
- include token/bot setup section with `[REQUEST FROM JINWANG]` marker.

**Tests:**
- docs mention Hermes source-untouched.
- service templates call ZeusOS CLI and use safe env file path, no secrets committed.

## 7. Verification plan

Required before commit/push:

```bash
PYTHONPATH=src pytest -q tests/test_zeus_schema.py tests/test_zeus_events.py tests/test_zeus_queue.py tests/test_zeus_cli.py tests/test_zeus_orchestrator.py tests/test_zeus_workers.py tests/test_zeus_approvals.py tests/test_zeus_projection.py tests/test_zeus_a2a.py tests/test_zeus_painter.py tests/test_zeus_image_generation.py tests/test_zeus_export.py
PYTHONPATH=src pytest -q
python -m compileall -q src/zeus_os tests
```

Security/static checks:

```bash
git diff --cached | grep '^+' | grep -iE '(api_key|secret|password|token|passwd)\s*=\s*["'"'].*["'"']' || true
git diff --cached | grep '^+' | grep -E 'os\.system\(|subprocess.*shell=True|\beval\(|\bexec\(|pickle\.loads?' || true
```

Independent review:
- architecture/runtime review
- security/ops review
- UX/operator review
- final diff review after fixes

Live Discord/gateway smoke is **not** automatic. If a new Discord bot/app token is required, stop at the documented setup point and request token/permissions from Jinwang.

## 8. Bot/token handoff point

Stop and ask Jinwang for bot/app/token only after these are complete:

1. CLI-only deterministic Zeus OS passes tests.
2. Discord plugin dry-run tests pass without live gateway restart.
3. `docs/zeus-os-operator-guide.md` names required Discord permissions/scopes.
4. No secrets are stored in repo.

Request format:

```text
진왕님, 이제 라이브 Discord boardroom 연결 단계입니다. 새 봇을 만들 경우 필요한 것은:
- Discord application/bot token
- client/application ID
- target guild/channel/thread policy
- permissions: send messages, create public threads, manage webhooks(optional), read message history, use slash commands/components
토큰 값은 채팅에 평문으로 남기지 말고 지정한 secret file/env 경로에 넣어주세요.
```

## 9. Commit and push policy

Commit only after:

- targeted Zeus tests pass,
- full feasible ZeusOS suite passes or unrelated failures are proven baseline/live-tool-only,
- independent review passes,
- no secrets detected,
- generated artifacts that should not be versioned are ignored,
- docs and usage guide are updated.

Commit message candidate:

```bash
git commit -m "feat: add Zeus OS control-plane foundation"
git push origin main
```

## 10. Open decisions

- Whether the live Discord boardroom uses the existing Hermes bot first or a new dedicated bot. MVP can use existing bot; new bot is cleaner if Jinwang wants separate identity/permissions.
- Whether named persona rendering uses webhooks in phase 1 or plain bot messages. Recommendation: plain bot messages first, webhook persona renderer later.
- Whether real OpenCode worker adapter ships in first implementation batch. Recommendation: deterministic worker first; OpenCode adapter after queue/approval/projection are stable.
- Whether live `gpt-image-2` adapter is enabled initially. Recommendation: fake adapter first; live adapter after cost/safety approval path is proven.
