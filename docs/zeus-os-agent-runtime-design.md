# Zeus OS Agent Runtime Design

**Date:** 2026-05-05
**Author:** external senior backend / agent-runtime review
**Scope:** migrate ZeusOS from Python CLI + SQLite + `data/` artifacts into a multi-agent Zeus OS boardroom runtime while keeping Hermes upstream/source untouched.

## Executive recommendation

Build Zeus OS as a ZeusOS-owned sidecar runtime, not as Hermes core changes and not as a Discord-first bot network. The canonical source of truth should be:

```text
Hermes Discord gateway / ZeusOS plugin
  -> enqueue-only interface commands and button callbacks
  -> state/zeus_os.db SQLite WAL blackboard + append-only event log
  -> zeus-orchestrator daemon: leases tasks, decomposes, assigns, gates approvals
  -> participant workers: long-lived adapters for deterministic, Hermes, OpenCode/Claude, shell
  -> data/zeus/tasks/<task_id>/ artifacts
  -> Discord threads/cards as projections only
```

The repo already has the right primitives to evolve incrementally: `pyproject.toml`, `src/zeus_os/cli.py`, SQLite-backed modules, artifact directories under `data/`, deterministic Minerva/Minerva workflow (`src/zeus_os/minerva.py`), tests, and Hermes Discord plugins under `plugins/`. Reuse those patterns.

## Personas: processes, DB agent cards, or Discord bots?

Use **DB agent cards as the identity layer**, **worker processes as execution capacity**, and **Discord bots/messages only as UI projection**.

| Concept | Recommended representation | Why |
|---|---|---|
| Persona / role such as Chair, PM, Researcher, Engineer, Critic, Scribe, Painter | `agent_cards` row with role, capabilities, prompt/config metadata | Durable, inspectable, A2A-projectable, independent of process restarts. |
| Running executor | `worker_agents` row plus OS process/tmux/session metadata | A role may have zero, one, or many workers; workers can die/restart without losing persona identity. |
| Discord presence | Usually one Boardroom/ZeusOS bot rendering cards; optional named webhooks later | Multiple Discord bots make auth, rate limits, recovery, and source-of-truth confusing. Use Discord names/avatar projection only after the DB model is stable. |

So: personas are **not primarily processes** and **not primarily Discord bots**. They are DB cards; processes lease work for those cards.

### Painter persona recommendation

Add **Painter** as a first-class creative/visual-synthesis persona, not as a one-off proposal helper. Painter's job is to turn user-provided content, boardroom decisions, research notes, code architecture, or product strategy into purpose-fit images/diagrams that convince, explain, or communicate to a named audience.

**Role boundary:** Painter owns visual intent, prompt/style artifacts, generation handoff, and visual QA. It does **not** silently invent unsupported facts, approve publication, bypass cost/safety gates, or mutate source files. PM/Chair remain responsible for clarifying purpose and acceptance criteria; Critic/QA remains responsible for independent review.

**Canonical flow:**

1. PM/Controller asks or infers a visual brief: purpose, audience, desired action/belief change, key content to include/exclude, medium/aspect ratio, style constraints, brand constraints, and factual claims that must be grounded.
2. Painter or an OpenCode design-team worker creates artifacts: `brief.md`, `prompt.md`, `style.md`, optional `composition.md`, and `review.md` checklist.
3. A gated image-generation worker calls `gpt-image-2` with the approved prompt/style bundle and writes `image.png` plus optional variants under `data/zeus/tasks/<task_id>/<work_order_id>/`.
4. Painter performs first-pass visual QA against the brief; Critic/QA can perform independent factual/safety/accessibility review before publication or user-facing use.
5. Scribe records final selected image, prompt provenance, known limitations, and user-visible caption/alt text.

**Capabilities to register:** `visual_briefing`, `diagram_prompting`, `image_prompting`, `style_direction`, `visual_critique`, `variant_selection`, `alt_text_captioning`, `gpt_image_2_handoff`. Use dynamic capability matching so Painter is only invited when a task asks for an image/diagram/visual artifact or when PM detects that visual explanation would materially improve the outcome.

**Inputs:** user-provided content; PM brief; required claims/evidence sources; audience; medium/channel; aspect ratio; style/brand constraints; negative constraints; privacy/safety classification; max variants/cost budget.

**Outputs:** `brief.md`, `prompt.md`, `style.md`, `review.md`, `image.png`, optional `variants/variant-*.png`, `selected.md`, `alt-text.md`, and registered artifact metadata including generator model, prompt hash, dimensions, seed/request id if available, and safety/cost approvals.

**OpenCode/gpt-image-2 split:** use OpenCode as the design-studio/planning/review executor that can read context and produce structured prompt/style/review files. Use `gpt-image-2` only inside a narrow image-generation adapter that consumes those files and returns images/metadata. This keeps creative reasoning auditable and image API use gated, retryable, and reproducible.

## Data-layer implementation recommendation

Adopt a three-temperature data hierarchy:

1. **Hot control plane: SQLite WAL** — canonical `tasks`, `work_orders`, `messages`, `approvals`, `decisions`, worker heartbeat, lease/claim state, append-only `task_events`, artifact metadata, and projection offsets. DuckDB/Iceberg must not replace this layer because Zeus OS needs frequent small transactional writes, idempotent retries, crash recovery, and approval enforcement.
2. **Artifact layer: filesystem** — prompts, logs, reports, diffs, generated images, media, and large outputs under `data/zeus/tasks/<task_id>/...`; SQLite stores URI, hash, size, media type, provenance, retention, and producer metadata.
3. **Warm analytics: DuckDB / Parquet exports** — read-mostly reporting over exported event/artifact metadata: latency, retry/failure rates, approval bottlenecks, worker utilization, cost/token trends, projection lag. DuckDB is not a runtime queue or lease owner.
4. **Cold archive later: Parquet/Iceberg/object storage** — only when long-retention, multi-machine analytics, object-store durability, or external query engines justify the operational cost.

Implementation backlog additions:

- Add SQLite PRAGMAs/migrations, atomic lease/claim/renew/recover methods, append-only event envelope with correlation/causation IDs, projection offsets, and startup recovery.
- Add atomic artifact registration: temp write, rename, hash/size/MIME capture, DB metadata insert, and reconciliation/GC job.
- Add `zeus export events --format parquet` and DuckDB report queries; keep them downstream from SQLite.
- Define future Iceberg trigger criteria rather than implementing Iceberg in MVP.

## Core invariants

1. **Interface enqueue-only:** Discord plugin, CLI enqueue, and future A2A HTTP adapter create messages/tasks/events/queue rows only. They never perform repo writes, shell commands, mail/calendar writes, or LLM coding work directly.
2. **SQLite is canonical:** Discord messages, thread titles, and buttons are projections. DB + artifacts must be enough to replay/export a boardroom.
3. **Append-only event log:** Every state mutation emits a `task_events` row with per-task sequence. Mutable tables are current-state indexes, not the audit trail.
4. **Artifacts are files:** Store large prompts, outputs, reports, diffs, screenshots, handoff JSON, and minutes in `data/zeus/tasks/<task_id>/...`; DB stores URI, hash, size, and metadata.
5. **Approval before side effects:** Any external side effect, repo mutation, gateway/systemd action, credential access, Discord configuration change, or costly long-running tool requires explicit gate approval.
6. **Hermes source untouched:** Zeus OS lives in ZeusOS repo modules/plugins/systemd units and calls Hermes as an external runtime/subprocess where needed.
7. **Deterministic first:** Every core flow has a fake/stub worker path before using real LLM/tool adapters.

## Proposed module and file layout

```text
src/zeus_os/zeus_os/
  __init__.py
  schema.py            # migrations/bootstrap, PRAGMAs, schema version
  store.py             # transactional repository methods
  ids.py               # deterministic ID helpers and validation
  events.py            # append/read/replay event helpers
  queue.py             # lease/ack/nack/recover primitives
  orchestrator.py      # daemon loop and work-order planner
  workers.py           # worker loop base classes and adapters
  approvals.py         # risk classification + approval gates
  projection.py        # Discord/markdown dashboard projection from DB
  cli.py               # subcommand handlers imported by main cli.py
plugins/hermes_zeus_gateway/__init__.py
  # Discord slash/text/button bridge: enqueue-only + projection render
scripts/zeus-orchestrator.service.template
scripts/zeus-worker.service.template
tests/test_zeus_schema.py
tests/test_zeus_queue.py
tests/test_zeus_orchestrator.py
tests/test_zeus_workers.py
tests/test_zeus_projection.py
tests/test_zeus_e2e.py
docs/zeus-os-agent-runtime-design.md
```

## Database schema

Use `state/zeus_os.db`, SQLite WAL, `PRAGMA foreign_keys=ON`, `busy_timeout=5000`, ISO-8601 UTC timestamps, JSON stored as TEXT, and integer `revision` fields for optimistic concurrency.

### Schema management

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_metadata (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### Agent cards and workers

```sql
CREATE TABLE IF NOT EXISTS agent_cards (
  agent_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  persona_type TEXT NOT NULL CHECK (persona_type IN ('chair','pm','researcher','engineer','critic','scribe','painter','executor','human','system')),
  description TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '1',
  model_policy_json TEXT NOT NULL DEFAULT '{}',
  capabilities_json TEXT NOT NULL DEFAULT '[]',
  skills_json TEXT NOT NULL DEFAULT '[]',
  safety_policy_json TEXT NOT NULL DEFAULT '{}',
  prompt_uri TEXT,
  endpoint_url TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','retired')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS worker_agents (
  worker_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agent_cards(agent_id),
  kind TEXT NOT NULL CHECK (kind IN ('deterministic','hermes','opencode','claude_code','image_generation','shell','http')),
  display_name TEXT NOT NULL,
  host TEXT,
  pid INTEGER,
  tmux_session TEXT,
  status TEXT NOT NULL CHECK (status IN ('starting','idle','busy','draining','stopped','failed')),
  capabilities_json TEXT NOT NULL DEFAULT '[]',
  current_work_order_id TEXT,
  heartbeat_at TEXT,
  lease_owner TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_worker_agents_status ON worker_agents(status, heartbeat_at);
CREATE INDEX IF NOT EXISTS idx_worker_agents_agent ON worker_agents(agent_id);
```

### Contexts, boardroom sessions, messages

```sql
CREATE TABLE IF NOT EXISTS contexts (
  context_id TEXT PRIMARY KEY,
  origin_platform TEXT NOT NULL DEFAULT 'cli',
  origin_guild_id TEXT,
  origin_channel_id TEXT,
  origin_thread_id TEXT,
  origin_message_id TEXT,
  user_id TEXT,
  title TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','archived','closed')),
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boardroom_sessions (
  session_id TEXT PRIMARY KEY,
  context_id TEXT NOT NULL REFERENCES contexts(context_id),
  title TEXT NOT NULL,
  goal TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('opened','agenda_setting','deliberating','deciding','assigning','blocked','closed','failed','canceled')),
  chair_agent_id TEXT REFERENCES agent_cards(agent_id),
  scribe_agent_id TEXT REFERENCES agent_cards(agent_id),
  active_agenda_id TEXT,
  revision INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_boardroom_context ON boardroom_sessions(context_id);

CREATE TABLE IF NOT EXISTS boardroom_participants (
  session_id TEXT NOT NULL REFERENCES boardroom_sessions(session_id),
  agent_id TEXT NOT NULL REFERENCES agent_cards(agent_id),
  role TEXT NOT NULL,
  display_name TEXT NOT NULL,
  speaking_policy_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'joined' CHECK (status IN ('invited','joined','muted','left','failed')),
  joined_at TEXT NOT NULL,
  last_seen_at TEXT,
  PRIMARY KEY (session_id, agent_id)
);

CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  context_id TEXT NOT NULL REFERENCES contexts(context_id),
  session_id TEXT REFERENCES boardroom_sessions(session_id),
  task_id TEXT,
  work_order_id TEXT,
  role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool','agent','human')),
  sender_agent_id TEXT REFERENCES agent_cards(agent_id),
  parts_json TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','operator','private')),
  metadata_json TEXT NOT NULL DEFAULT '{}',
  reference_task_ids_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_context_created ON messages(context_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_task ON messages(task_id, created_at);
```

### Tasks, agenda, decisions, approvals

```sql
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  context_id TEXT NOT NULL REFERENCES contexts(context_id),
  session_id TEXT REFERENCES boardroom_sessions(session_id),
  parent_task_id TEXT REFERENCES tasks(task_id),
  title TEXT NOT NULL,
  user_goal TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('submitted','working','input_required','auth_required','approval_required','blocked','completed','failed','canceled','rejected')),
  priority INTEGER NOT NULL DEFAULT 100,
  risk_level TEXT NOT NULL DEFAULT 'low' CHECK (risk_level IN ('low','medium','high','critical')),
  assigned_orchestrator_id TEXT,
  current_worker_id TEXT,
  status_message TEXT NOT NULL DEFAULT '',
  progress_percent INTEGER NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
  result_summary TEXT NOT NULL DEFAULT '',
  idempotency_key TEXT,
  revision INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  UNIQUE(context_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_tasks_state_priority ON tasks(state, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id, created_at);

CREATE TABLE IF NOT EXISTS agenda_items (
  agenda_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES boardroom_sessions(session_id),
  task_id TEXT REFERENCES tasks(task_id),
  title TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('proposed','active','waiting','deciding','assigned','done','dropped')),
  owner_agent_id TEXT REFERENCES agent_cards(agent_id),
  priority INTEGER NOT NULL DEFAULT 100,
  decision_required INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agenda_session_status ON agenda_items(session_id, status, priority);

CREATE TABLE IF NOT EXISTS decisions (
  decision_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES boardroom_sessions(session_id),
  agenda_id TEXT REFERENCES agenda_items(agenda_id),
  task_id TEXT REFERENCES tasks(task_id),
  title TEXT NOT NULL,
  decision_text TEXT NOT NULL,
  rationale_summary TEXT NOT NULL DEFAULT '',
  dissent_summary TEXT NOT NULL DEFAULT '',
  risk_level TEXT NOT NULL DEFAULT 'low',
  status TEXT NOT NULL CHECK (status IN ('proposed','needs_human','approved','rejected','superseded','expired')),
  proposed_by TEXT REFERENCES agent_cards(agent_id),
  decided_by TEXT,
  supersedes_decision_id TEXT REFERENCES decisions(decision_id),
  revision INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  decided_at TEXT,
  expires_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status, expires_at);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  decision_id TEXT REFERENCES decisions(decision_id),
  task_id TEXT REFERENCES tasks(task_id),
  work_order_id TEXT,
  gate_type TEXT NOT NULL CHECK (gate_type IN ('repo_write','external_side_effect','credential_access','discord_config','gateway_restart','cost_budget','human_input','destructive_action')),
  status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','expired','canceled')),
  requested_by TEXT,
  approved_by TEXT,
  reason TEXT NOT NULL DEFAULT '',
  scope_json TEXT NOT NULL DEFAULT '{}',
  idempotency_key TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_approvals_pending ON approvals(status, gate_type, created_at);
```

### Event log, queue, work orders, artifacts, projection

```sql
CREATE TABLE IF NOT EXISTS task_events (
  event_id TEXT PRIMARY KEY,
  task_id TEXT REFERENCES tasks(task_id),
  session_id TEXT REFERENCES boardroom_sessions(session_id),
  context_id TEXT REFERENCES contexts(context_id),
  event_type TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('interface','orchestrator','worker','human','system')),
  actor_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  UNIQUE(task_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_task_events_task_seq ON task_events(task_id, sequence);
CREATE INDEX IF NOT EXISTS idx_task_events_session_time ON task_events(session_id, created_at);

CREATE TABLE IF NOT EXISTS work_orders (
  work_order_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  session_id TEXT REFERENCES boardroom_sessions(session_id),
  parent_work_order_id TEXT REFERENCES work_orders(work_order_id),
  worker_kind TEXT NOT NULL,
  capability_required TEXT NOT NULL DEFAULT '',
  assigned_agent_id TEXT REFERENCES agent_cards(agent_id),
  instruction_summary TEXT NOT NULL,
  instruction_path TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('ready','leased','running','approval_required','completed','failed','canceled','dead')),
  lease_owner TEXT,
  lease_expires_at TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  heartbeat_at TEXT,
  result_summary TEXT NOT NULL DEFAULT '',
  error_summary TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_work_orders_ready ON work_orders(state, worker_kind, lease_expires_at, created_at);
CREATE INDEX IF NOT EXISTS idx_work_orders_task ON work_orders(task_id, created_at);

CREATE TABLE IF NOT EXISTS bus_queue (
  queue_id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  key TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('ready','leased','acked','dead','canceled')),
  lease_owner TEXT,
  lease_expires_at TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5,
  available_at TEXT NOT NULL,
  idempotency_key TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(topic, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_bus_queue_claim ON bus_queue(topic, state, available_at, lease_expires_at, created_at);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  task_id TEXT REFERENCES tasks(task_id),
  session_id TEXT REFERENCES boardroom_sessions(session_id),
  work_order_id TEXT REFERENCES work_orders(work_order_id),
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL CHECK (kind IN ('prompt','style','review','report','minutes','handoff','diff','log','image','audio','data','decision_record','other')),
  media_type TEXT NOT NULL DEFAULT 'text/plain',
  uri TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id, created_at);

CREATE TABLE IF NOT EXISTS dashboard_messages (
  dashboard_id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES boardroom_sessions(session_id),
  task_id TEXT REFERENCES tasks(task_id),
  platform TEXT NOT NULL DEFAULT 'discord',
  guild_id TEXT,
  channel_id TEXT NOT NULL,
  thread_id TEXT,
  message_id TEXT,
  card_kind TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 0,
  last_rendered_hash TEXT,
  last_rendered_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_unique_card ON dashboard_messages(platform, channel_id, COALESCE(thread_id,''), card_kind, COALESCE(session_id,''), COALESCE(task_id,''));
```

## Queue and lease semantics

### Topics

Use topic names to make ownership explicit:

- `interface.inbox`: raw user/API/Discord enqueue events.
- `orchestrator.inbox`: tasks needing planning/state transition.
- `session.<session_id>.floor`: boardroom turns needing floor-control processing.
- `worker.<kind>`: executable work orders, e.g. `worker.deterministic`, `worker.opencode`, `worker.image_generation`.
- `projection.discord`: render/update Discord dashboards.
- `approval.inbox`: approval card creation and resolution handling.
- `maintenance.recover`: periodic stale lease recovery and metrics snapshots.

### Claim algorithm

SQLite does not have `SELECT FOR UPDATE`; use `BEGIN IMMEDIATE` with a small transaction:

```sql
-- Pseudocode inside BEGIN IMMEDIATE
SELECT queue_id
FROM bus_queue
WHERE topic = :topic
  AND state = 'ready'
  AND available_at <= :now
  AND (lease_expires_at IS NULL OR lease_expires_at < :now)
ORDER BY available_at ASC, created_at ASC
LIMIT :n;

UPDATE bus_queue
SET state = 'leased',
    lease_owner = :worker_id,
    lease_expires_at = :now_plus_lease,
    attempt_count = attempt_count + 1,
    updated_at = :now
WHERE queue_id IN (...)
  AND state = 'ready';
COMMIT;
```

Lease defaults:

- Queue item lease: 60 seconds.
- Work order lease: 120 seconds for deterministic/shell, 300 seconds for LLM/coding agents.
- Heartbeat cadence: every 15-30 seconds.
- Stale worker: no heartbeat for 2x lease duration.
- Backoff: `available_at = now + min(2^attempt_count * 10s, 15m) + jitter`.
- Dead-letter: if `attempt_count >= max_attempts`, set `state='dead'`, append failure event, render dashboard alert.

### Ack, nack, renew, cancellation

- **Ack:** in one transaction mark queue row `acked`, update work order/task state, append event.
- **Retry/nack:** set queue row `ready`, clear lease, set future `available_at`, append `queue.retry` event with summarized error.
- **Dead:** set queue/work order `dead`; no silent failures.
- **Renew:** only the current `lease_owner` can extend `lease_expires_at`; renewal also updates `worker_agents.heartbeat_at`.
- **Cancel:** user/orchestrator writes a cancel event; queue/work order transitions to `canceled`. Worker adapters must poll cancellation between tool calls; they cannot interrupt arbitrary subprocesses safely without adapter-specific cancellation.
- **Idempotency:** interface commands and button callbacks pass idempotency keys. Queue table has `UNIQUE(topic, idempotency_key)` so Discord retries do not duplicate tasks.

### Transaction boundaries

Every operation that mutates state must follow:

1. validate command and current revision;
2. `BEGIN IMMEDIATE`;
3. mutate current-state table;
4. append event with next per-task sequence;
5. enqueue projection/next-work item;
6. commit;
7. perform non-canonical side effect, if any, only after approval and with a resumable handoff record.

## Orchestrator lifecycle

### Daemon commands

Add CLI commands:

```bash
PYTHONPATH=src python -m zeus_os.cli zeus bootstrap --config config/pipeline.yaml
PYTHONPATH=src python -m zeus_os.cli zeus enqueue --goal "..." --origin-platform cli
PYTHONPATH=src python -m zeus_os.cli zeus orchestrator --config config/pipeline.yaml --once
PYTHONPATH=src python -m zeus_os.cli zeus worker --kind deterministic --config config/pipeline.yaml --once
PYTHONPATH=src python -m zeus_os.cli zeus status --task-id ... --format markdown
PYTHONPATH=src python -m zeus_os.cli zeus replay --task-id ... --format json
PYTHONPATH=src python -m zeus_os.cli zeus export --session-id ... --format markdown
```

### Startup

1. Open DB with WAL + `foreign_keys=ON`.
2. Register `worker_agents` row for daemon identity.
3. Recover own abandoned leases from previous PID/session.
4. Load enabled `agent_cards` and capability matrix.
5. Enter poll loop with jittered sleep and clean shutdown handlers.

### Orchestration loop

For each claimed item from `orchestrator.inbox`:

1. Read task/session/event slice and artifacts index.
2. If task is new, create boardroom session and agenda items as needed.
3. Classify risk and decide whether an approval row is required.
4. If approval required, set task `approval_required`, enqueue `approval.inbox`, stop.
5. Create work orders for participant turns:
   - Chair/PM: agenda framing and acceptance criteria.
   - Researcher: evidence gathering/read-only repo/docs review.
   - Engineer: implementation approach and file impact.
   - Painter: visual brief, image/diagram prompt, style direction, and visual QA when visual output is requested or useful.
   - Critic/QA: risks, missing tests, failure modes.
   - Scribe: minutes/decision summary.
6. Enqueue `worker.<kind>` rows for ready work orders.
7. Enqueue `projection.discord` update.

### Shutdown

- Stop claiming new queue rows.
- Mark worker `draining`.
- Finish current transaction/work item or release lease as retryable.
- Update `worker_agents.status='stopped'` and append lifecycle event.

## Worker adapter lifecycle

### Base contract

Input:

- `work_orders.instruction_path` file.
- relevant task/session event slice.
- allowed artifact URIs.
- capability and safety policy.
- cancellation token from DB.

Output:

- artifact(s) under `data/zeus/tasks/<task_id>/<work_order_id>/`.
- concise `messages` row.
- `task_events` row with `work_order.completed` or `work_order.failed`.
- no private chain-of-thought; store `rationale_summary`, evidence, confidence, assumptions, open questions.

### Adapter sequence

1. Claim `worker.<kind>` queue row and corresponding `work_orders` row.
2. Set work order `running`, heartbeat.
3. Materialize sandbox/handoff directory.
4. Execute adapter:
   - `deterministic`: pure Python stub for tests and dry runs.
   - `hermes`: subprocess using Hermes CLI/API with explicit prompt/artifact contract.
   - `opencode` / `claude_code`: tmux handoff or CLI run with worktree/scope guard.
   - `image_generation`: narrow adapter for `gpt-image-2` or successor image models; consumes approved `prompt.md`/`style.md`, writes images plus metadata, and performs no planning itself.
   - `shell`: allowlisted commands only.
5. Hash and register artifacts.
6. Ack queue and mark work order complete; update task/session aggregate if all required work is done.
7. On error, write error artifact, retry or dead-letter based on attempts.

## Discord projection

The Discord plugin should live in `plugins/hermes_zeus_gateway/` and enforce:

- `/zeus start <goal>` creates DB context/task/event/queue row first, then creates or updates a thread/card.
- Button callback payload contains `session_id`, `task_id` or `decision_id`, `revision`, and idempotency key.
- Callback validates channel/thread binding from `dashboard_messages` before appending approval/decision event.
- Revision mismatch is rejected with a fresh card render.
- Discord message deletion is non-fatal; `zeus status`/projection recreates cards from DB.
- Discord content is compact: status, next action, pending approvals, artifact links/summaries. No raw DB IDs unless operator mode.

## Safety gates

### Default gate matrix

| Action | Gate |
|---|---|
| Read repo/docs/artifacts | allowed for read-only workers |
| Write under `data/zeus/` | allowed after task creation |
| Modify `src/`, `tests/`, `plugins/`, `scripts/`, `docs/` | `repo_write` approval |
| Run tests/builds | allowed after repo-write approval or explicit dev-cycle command |
| Shell command beyond allowlist | `external_side_effect` approval |
| Network calls | `external_side_effect` unless read-only public fetch is explicitly allowed |
| Image generation with `gpt-image-2` or equivalent | `cost_budget`; add `human_input`/publication approval if using personal likenesses, sensitive content, brand assets, or public-facing distribution |
| Secrets/mail/calendar/Drive access | `credential_access` approval |
| Discord channel config, pins, roles, bot settings | `discord_config` approval |
| Hermes gateway/systemd/cron restart/update | `gateway_restart` approval |
| Expensive model/coding-agent run | `cost_budget` approval |

### Scope enforcement

- Every approval stores `scope_json`: paths, commands, external endpoints, duration, budget, and max attempts.
- Workers check approval row before side effects and append `approval.checked` event.
- Use path allowlists rooted at `/home/jinwang/workspace/zeus-os`; never assume `/workspace/...`.
- Redact token-like strings before storing messages/artifacts.
- Generated-image artifacts must retain prompt/style provenance, safety decision, and alt text; never store private/source images or likeness inputs outside approved artifact scope.

## Implementation lifecycle and dev cycle

### Phase 0 — Discovery and contracts

Acceptance:

- Inventory existing CLI, Minerva, plugin, state DB, artifact paths, and tests.
- Produce this design and a migration checklist.
- No runtime behavior changes.

Tasks:

1. Read `src/zeus_os/cli.py`, `runtime.py`, `minerva.py`, existing plugins/tests.
2. Confirm artifact roots: `state/`, `data/`, `data/minerva/`.
3. Define Zeus invariants and acceptance criteria.

### Phase 1 — Schema/bootstrap/store

Acceptance:

- `zeus bootstrap` creates `state/zeus_os.db` and all tables/idempotent indexes.
- WAL/foreign-key PRAGMAs are applied.
- Golden schema test passes in temp workspace.
- No Discord required.

Tests:

- schema table/index existence.
- migration idempotency.
- foreign-key rejection.
- JSON default validity.
- artifact root creation.

### Phase 2 — Queue/lease primitives

Acceptance:

- Queue supports enqueue, claim, renew, ack, retry/backoff, dead-letter, cancel.
- Concurrent claim test proves only one owner gets a row.
- Expired lease is reclaimed; non-expired lease is not.

Tests:

- unit tests with temp SQLite.
- property-like test for repeated retries reaching dead state.
- multiprocessing/threaded contention test using separate connections.
- idempotency test for duplicate Discord retry.

### Phase 3 — CLI-only Zeus task lifecycle

Acceptance:

- `zeus enqueue --goal` creates context/task/event/queue rows and task artifact directory.
- `zeus status` renders markdown/json from DB.
- `zeus replay` reconstructs state from events.

Tests:

- CLI parser/unit tests.
- event sequence monotonicity.
- replay equals current-state projection for deterministic scenario.

### Phase 4 — Orchestrator daemon MVP

Acceptance:

- `zeus orchestrator --once` claims new task and creates a boardroom session, agenda, decisions as needed, and at least three participant work orders.
- Orchestrator does not execute worker side effects directly.
- Failure emits event and projection queue row.

Tests:

- deterministic orchestration fixtures.
- risk classifier/gate tests.
- stuck lease recovery.
- daemon `--once` smoke.

### Phase 5 — Deterministic worker adapter

Acceptance:

- `zeus worker --kind deterministic --once` completes participant work orders and writes artifacts.
- All artifacts are hash-registered in DB.
- Scribe produces minutes artifact after participant reports.

Tests:

- worker success.
- worker failure/retry/dead-letter.
- artifact hash/size/media-type registration.
- no private reasoning fields in persisted outputs.

### Phase 6 — Approval gates

Acceptance:

- Side-effect work orders stop in `approval_required` until approved.
- Approval callback/CLI can approve/reject with revision checks.
- Rejected gate cancels or replans dependent work.

Tests:

- repo-write gate required before code-modifying worker.
- gateway restart gate required for systemd/Hermes actions.
- stale revision rejection.
- idempotent approve/reject.

### Phase 7 — Discord projection plugin

Acceptance:

- Discord start/status/approval flows append DB events first and render cards second.
- Gateway restart or Discord message deletion does not lose task state.
- Callback channel/thread/revision mismatch is rejected.

Tests:

- pure plugin tests with fake Discord source/adapter.
- projection renderer snapshot tests.
- button payload validation tests.
- no direct worker execution from plugin test.

### Phase 8 — Real worker adapters

Acceptance:

- Hermes subprocess and one coding-agent handoff adapter are available behind approvals.
- Painter/OpenCode design handoff and `image_generation`/`gpt-image-2` adapter are available behind cost/safety approvals.
- Adapter writes handoff artifacts and final summaries, not hidden state.
- Cancellation/retry behavior is documented and tested with fake processes.

Tests:

- fake subprocess adapter.
- tmux/session metadata registration.
- fake `gpt-image-2` adapter that consumes `prompt.md`/`style.md` and registers deterministic image metadata.
- command/path allowlist enforcement.
- cancellation between steps.

### Phase 9 — Observability and operations

Acceptance:

- `zeus status --ops` shows queue lag, stuck leases, worker heartbeats, dead letters, pending approvals, last event time.
- `zeus doctor` validates DB, artifacts, worker liveness, Discord projection drift.
- systemd unit templates exist for orchestrator and workers.

Tests:

- ops metrics calculation.
- doctor detects stale worker/stale lease/missing artifact/hash mismatch.
- unit rendering tests using existing runtime test style.

### Phase 10 — E2E and rollout

Acceptance:

- End-to-end CLI-only scenario completes without network.
- Discord dry-run scenario creates projected card payloads without sending live messages.
- Live Discord activation requires operator approval.

E2E scenario:

1. bootstrap DB;
2. enqueue goal: “Design persistent boardroom callback recovery”;
3. orchestrator creates agenda and work orders;
4. deterministic workers produce chair/researcher/engineer/critic/scribe outputs;
5. decision proposed;
6. approval granted via CLI fake human;
7. minutes exported;
8. replay matches exported state;
9. projection can recreate Discord cards from DB.

## Acceptance criteria for the whole migration

1. Hermes upstream source remains untouched.
2. Interface plugin is enqueue/render only; tests prove it cannot run worker adapters.
3. `state/zeus_os.db` + `data/zeus/tasks/` can replay/export boardroom state without Discord.
4. SQLite lease queue prevents duplicate execution under concurrent claim tests.
5. Worker death/restart produces retry/dead-letter events and visible operator status.
6. At least six DB agent personas exist, including Painter, and can each produce a deterministic participant artifact.
7. Approval gates block repo writes, external side effects, credentials, Discord config, and gateway restart actions until explicit approval.
8. Discord thread projection supports status cards, decision cards, revision mismatch handling, and recovery after message deletion/restart.
9. CLI-only E2E and Discord dry-run E2E pass in CI/local `pytest`.
10. Observability commands expose queue lag, stuck leases, dead letters, worker heartbeat, pending approvals, artifact hash failures.

## Specific test categories

- **Schema/migration:** table/index existence, FK constraints, idempotent migrations, PRAGMAs, schema versioning.
- **Store/repository:** transactional state + event append, sequence numbering, optimistic concurrency revisions, idempotency keys.
- **Queue/lease:** claim, renew, ack, nack, retry backoff, dead-letter, cancel, concurrent claim, expired lease recovery.
- **Orchestrator:** decomposition, role assignment, risk classification, no direct side effects, retry on planner failure.
- **Worker adapters:** deterministic outputs, artifact writes, failure handling, heartbeat, cancellation, allowlist/gate enforcement.
- **Approval gates:** pending/approve/reject/expire, stale revision, scope validation, dependent task cancellation/replan.
- **Projection:** markdown/card rendering, Discord payload validation, channel/thread mismatch, deleted message recovery, no source-of-truth leakage.
- **E2E:** CLI-only deterministic run, Discord dry-run, replay/export equivalence, restart recovery, artifact integrity.
- **Observability/ops:** queue lag, dead letters, stuck leases, stale workers, hash mismatch, doctor command.
- **Security/privacy:** secret redaction, no private reasoning persistence, path traversal rejection, workspace root enforcement.
- **Compatibility/A2A:** internal projection to AgentCard, Message.parts, TaskStatus, Artifact; no premature full protocol dependency.

## Rollout plan

1. **Shadow mode:** CLI-only, deterministic worker, no Discord live side effects. Store in `state/zeus_os.db` separate from `personal_intel.db` and `minerva.db`.
2. **Discord dry-run:** plugin renders payload artifacts rather than sending live messages; verify recovery and button payloads.
3. **Single-channel pilot:** enable `/zeus start/status` and approval cards in a private boardroom channel; deterministic workers only.
4. **One real adapter:** enable read-only Hermes/research adapter behind approval; no repo writes.
5. **Coding handoff adapter:** enable OpenCode/Claude handoff for approved repo-write tasks; require task-scoped worktree/path policy.
6. **Painter/image pilot:** enable OpenCode design-studio artifacts and a fake/then-live `gpt-image-2` adapter behind explicit cost/safety approval; publish only after review/alt-text artifacts exist.
7. **Always-on daemon:** install systemd user units for orchestrator + selected workers after `zeus doctor` passes.
8. **A2A thin adapter:** only after internal model stabilizes; expose `GET /agent-card`, `POST /message:send`, `GET /tasks/{id}`, events later.

## Non-goals for MVP

- Do not add Redis/NATS/Kafka/Temporal/Celery before SQLite lease limits are measured.
- Do not implement full A2A/SSE streaming first.
- Do not run one Discord bot per persona for MVP.
- Do not persist private chain-of-thought or raw tool logs by default.
- Do not let orchestrator become an executor.

## Immediate next implementation steps

1. Create `src/zeus_os/zeus_os/schema.py` with migration bootstrap and tests.
2. Create `store.py`, `events.py`, `queue.py` with transactional helpers and queue tests.
3. Wire `zeus bootstrap/enqueue/status/replay` into `src/zeus_os/cli.py`.
4. Implement `orchestrator --once` and deterministic `worker --once`.
5. Seed a `painter` agent card with visual capabilities and add deterministic Painter artifacts (`brief.md`, `prompt.md`, `style.md`, `review.md`) to the worker fixture path.
6. Add an approved `image_generation` worker adapter boundary for `gpt-image-2` that consumes Painter/OpenCode artifacts and registers `image.png`/variants with prompt/style provenance.
7. Add projection renderer and fake Discord plugin tests before any live Discord activation.
