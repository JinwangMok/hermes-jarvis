# Zeus OS A2A / Blackboard Protocol Review

**Reviewer:** external senior agent-protocol architect
**Scope:** evaluate whether SQLite blackboard-only collaboration is enough, whether A2A is overkill, and how to add real A2A without breaking Zeus OS's durable/replayable blackboard design.

## Executive recommendation

Keep the current SQLite blackboard/event-log/work-order design as the canonical coordination layer. Do **not** make A2A the internal bus or the primary orchestration model for MVP.

Add A2A now only as a **schema-compatible projection boundary** and later as a **thin HTTP adapter**:

```text
CLI / Discord / A2A HTTP adapter
  -> validates + normalizes incoming AgentCard/Message/Task-style requests
  -> writes canonical DB rows: contexts, tasks, messages, artifacts, events, queue
  -> orchestrator leases/plans bounded work orders
  -> workers write artifacts + events
  -> projection layer exposes A2A Task/Message/Artifact views from DB
```

This gives Zeus OS real under-the-hood agent communication without free-form infinite chat, while preserving replay, approvals, bounded rounds, and registry-based agent membership.

## Is blackboard-only enough?

Yes for MVP and for single-host/local-sidecar Zeus OS. A durable blackboard plus append-only events is a better internal primitive than direct agent-to-agent chat because it gives:

- **Replayability:** DB + artifact hashes can reconstruct boardroom state without Discord or live processes.
- **Crash recovery:** workers can die, leases expire, and work resumes from durable work orders.
- **Idempotency:** retries from Discord, CLI, or future HTTP can be deduped with idempotency keys.
- **Governance:** approvals, revisions, and gate scope are enforceable before side effects.
- **Observability:** queue lag, dead letters, stale workers, pending approvals, and artifacts are inspectable.
- **Bounded coordination:** the orchestrator grants floor/turns; agents do not recursively chat forever.

The current design is not a passive blackboard if `bus_queue`, `work_orders`, leases, events, and projection topics are implemented. It is effectively a small durable workflow engine. That is exactly the right center of gravity.

The main caveat: blackboard-only must not devolve into agents polling an unstructured shared transcript. Use typed commands/events, ownership, leases, turn budgets, and agenda/session state machines.

## Is A2A overkill?

Full A2A as the internal architecture is overkill now. A2A is useful as an interoperability and projection protocol, but it should not replace the canonical state model.

A2A is overkill for MVP if it means:

- direct free-form agent chat as the coordination substrate;
- SSE/streaming everywhere before deterministic replay works;
- one process/bot per persona as a protocol requirement;
- remote agent auth, discovery, network retries, and payload compatibility before local queues are stable;
- treating transient protocol messages as source of truth.

A2A is not overkill if scoped to:

- an **external adapter** that accepts A2A-shaped requests and enqueues tasks/messages;
- an **export/projection** that maps DB rows to AgentCard, Message, Task, TaskStatus, and Artifact;
- a **remote-worker adapter** where an external A2A-capable agent is just another `worker_kind='http'` executor behind leases and approvals.

So the answer is: **A2A now as compatibility contract, later as edge transport; never as canonical state.**

## Architecture options

### Option 1 — Blackboard-only MVP

**Shape**

- SQLite WAL DB with typed tables: `agent_cards`, `worker_agents`, `contexts`, `messages`, `tasks`, `work_orders`, `task_events`, `artifacts`, `approvals`, `bus_queue`.
- Orchestrator creates bounded work orders from tasks.
- Workers claim work via leases, write artifacts/events, and never coordinate by unbounded chat.
- Discord is only projection.

**Pros**

- Fastest path to reliable local system.
- Strongest replay/recovery semantics.
- Minimal protocol surface and auth complexity.
- Easy to test deterministically.

**Cons**

- Less interoperable with external agent ecosystems initially.
- If event/message schemas are too ad hoc, later A2A mapping may be awkward.

**When to choose**

- MVP, single-machine boardroom, deterministic workers, first Hermes/OpenCode adapters.

### Option 2 — A2A-first internal bus

**Shape**

- Agents primarily exchange A2A Messages/Tasks with each other.
- DB stores logs/projections of protocol traffic.
- Orchestration emerges from agent conversation.

**Pros**

- Protocol-pure and potentially interoperable from day one.
- Easier to demo as “agents talking to agents.”

**Cons**

- Harder replay and idempotency.
- Conversation loops become the default failure mode.
- Approval gates are harder to enforce uniformly.
- Network/protocol lifecycle becomes coupled to core state transitions.
- Discord-vs-A2A-vs-DB source-of-truth ambiguity.

**Recommendation**

- Do not use this for Zeus OS.

### Option 3 — Blackboard core + A2A projection/adapter

**Shape**

- Keep DB as source of truth.
- Add A2A-compatible fields and mapping functions now.
- Add a thin A2A HTTP ingress/egress adapter once core lifecycle is stable.
- Remote A2A agents are registered in `agent_cards` and invoked through `work_orders` like any other worker.

**Pros**

- Preserves durable/replayable state.
- Gives real under-the-hood communication without free-form chat.
- Supports external interoperability later.
- Keeps Discord as projection only.
- Lets agent membership be managed by registry rows, not process topology.

**Cons**

- Requires disciplined schema mapping.
- Some A2A fields will be projections, not native DB columns.
- Streaming/event subscriptions should wait until idempotent task status works.

**Recommendation**

- Choose this.

## What “real A2A” should mean in Zeus OS

Real A2A should not mean agents DM each other indefinitely. It should mean the system can expose and consume A2A-style resources while every meaningful transition is backed by canonical DB events.

### AgentCard

Map from `agent_cards` plus worker availability:

- `agent_id` -> AgentCard `id`/stable URL slug.
- `name`, `description`, `version` -> AgentCard display fields.
- `capabilities_json`, `skills_json` -> capabilities/skills.
- `endpoint_url` -> external URL for remote agents or local A2A adapter URL for Zeus personas.
- `status` -> active/disabled/retired projection.
- `safety_policy_json`, `model_policy_json` -> metadata/security schemes.

Add if missing:

- `agent_cards.protocols_json` — supported protocols/transports, e.g. `[{"name":"a2a","version":"..."}]`.
- `agent_cards.registry_metadata_json` — owner, trust tier, allowed scopes, registration source.

### Message

Map `messages.parts_json` directly to A2A Message parts. Require typed parts, not arbitrary transcript text only:

- text part: concise user/agent message;
- artifact reference part: `artifact_id`, URI, hash, media type;
- task reference part: `task_id`;
- approval request/resolution part: `approval_id`, revision, scope summary;
- decision part: `decision_id`, status.

Rules:

- Persist summaries and evidence, not private chain-of-thought.
- Messages are observations/projections; task state changes must still be represented as `task_events`.
- Every incoming A2A message gets an idempotency key and origin metadata.

### Task / TaskStatus

Map `tasks` to A2A Task:

- `task_id` -> Task id.
- `title`, `user_goal` -> task name/description.
- `state` -> TaskStatus mapping.
- `progress_percent`, `status_message`, `result_summary` -> status detail.
- `context_id`, `session_id`, `parent_task_id` -> metadata/relations.
- `risk_level`, approvals -> Zeus-specific metadata.

Suggested status mapping:

| Zeus `tasks.state` | A2A-style status |
|---|---|
| `submitted` | `submitted` / `pending` |
| `working` | `working` |
| `input_required` | `input-required` |
| `auth_required` | `auth-required` |
| `approval_required` | `approval-required` or `input-required` with approval metadata |
| `blocked` | `blocked` |
| `completed` | `completed` |
| `failed` | `failed` |
| `canceled` | `canceled` |
| `rejected` | `rejected` |

### Artifact

Map `artifacts` to A2A Artifact:

- `artifact_id`, `name`, `description`, `kind`;
- `media_type`;
- `uri` or signed/local retrieval endpoint;
- `sha256`, `size_bytes`;
- `created_by`, `created_at`;
- `task_id`, `work_order_id`, `session_id` relations.

Do not inline large artifacts into messages. Use references plus hashes.

## Minimal A2A adapter structure

Add module boundaries like:

```text
src/zeus_os/zeus_os/a2a/
  models.py       # Pydantic/dataclass schemas for supported AgentCard/Message/Task/Artifact subset
  mapping.py      # DB <-> A2A projection functions
  ingress.py      # validate A2A requests, write canonical DB commands/events
  egress.py       # fetch/projection handlers from DB
  server.py       # optional FastAPI/HTTP adapter later
  tests/
```

### Initial endpoints

Start with a tiny, non-streaming surface:

- `GET /agent-card` — returns Zeus boardroom/registry card.
- `GET /agents/{agent_id}/card` — returns a registered persona/remote agent projection.
- `POST /message:send` — validates message, creates/updates context/task/message/event/queue row, returns task id/status.
- `GET /tasks/{task_id}` — returns Task projection from DB.
- `GET /tasks/{task_id}/artifacts` — returns registered artifact projections.

Defer:

- SSE/event streaming;
- push subscriptions;
- remote agent-to-agent negotiation;
- multi-tenant auth beyond local operator token/trust tiers;
- arbitrary task cancellation over A2A until cancellation semantics are implemented in workers.

## Bounded collaboration rules

To prevent free-form infinite chat, make the orchestrator own turn-taking:

- `boardroom_sessions.metadata_json.max_rounds`, default 2–3.
- `agenda_items.metadata_json.turn_budget`, e.g. max one response per role per agenda phase.
- `work_orders.parent_work_order_id` for explicit dependencies only.
- `session.<session_id>.floor` queue topic for turn grants.
- The Chair/Scribe may summarize and close; only the orchestrator can create new rounds.
- New tasks spawned by agents require a typed `task.proposed` event and either explicit user approval or bounded auto-approval policy.

A2A messages can request work, but cannot directly hand unbounded work to another worker. They become proposed tasks/work orders subject to policy.

## Human approval gates

Keep approval gates in the DB and expose them through A2A as task/input-required status and approval artifacts/messages.

Rules:

- Any repo write, external side effect, credential access, gateway/systemd change, Discord config, destructive action, or cost-budgeted run creates an `approvals` row.
- Approval scope must include paths, commands, endpoints, budget/duration, and max attempts.
- A2A can submit an approval response, but the adapter must validate actor, revision, idempotency key, and scope.
- Workers check approval rows inside their adapter before side effects and append `approval.checked` events.

## Agent addition/removal via registry

Use `agent_cards` as the registry and make workers capacity attached to cards.

Add/maintain operations:

- `zeus agent register --name ... --capability ... --endpoint-url ... --trust-tier ...`
- `zeus agent disable <agent_id>` — stops new assignments; existing work drains or cancels by policy.
- `zeus agent retire <agent_id>` — immutable history remains replayable.
- `zeus worker register/heartbeat/drain` for execution capacity.

Registry policy fields should include:

- capabilities and allowed task kinds;
- trust tier: local, trusted remote, untrusted remote;
- allowed side-effect scopes;
- required approval gates;
- protocol support: local, subprocess, Hermes, OpenCode, A2A HTTP.

Never delete historical agent cards used by events; mark disabled/retired.

## Can A2A be added now?

Yes, but only the compatibility layer should be added now:

1. Freeze canonical invariants: DB/event log/artifacts remain source of truth.
2. Ensure existing tables carry enough A2A-compatible structure: AgentCard, Message parts, TaskStatus, Artifact.
3. Add pure mapping tests: DB fixture -> A2A projection -> stable JSON snapshot.
4. Add A2A ingress tests: duplicate `message:send` idempotency, invalid agent/card rejection, no direct worker execution.
5. Add HTTP server only after CLI-only lifecycle and deterministic workers pass.

Do not wait to make the schema A2A-shaped; do wait to expose real network A2A until replay, approvals, queue leases, and worker lifecycle are correct.

## Recommended implementation sequence

1. **Keep current Phase 1–6 priority:** schema, store, queue, CLI lifecycle, orchestrator, deterministic workers, approvals.
2. **During schema work:** add A2A-compatible metadata fields and typed `parts_json` conventions.
3. **After deterministic worker:** add `a2a/mapping.py` and projection tests for AgentCard/Message/Task/Artifact.
4. **After approvals:** add A2A ingress as an enqueue-only local function, no HTTP server required.
5. **After Discord dry-run:** add minimal HTTP endpoints behind local/operator auth.
6. **After real worker adapter:** allow remote A2A agents as `worker_kind='http'`, invoked by work orders and constrained by leases/approvals.
7. **Only after stability:** add streaming/subscriptions if there is a concrete consumer.

## Key design guardrails

- Canonical state is always DB + artifacts, never Discord or A2A wire traffic.
- Protocol adapters are enqueue/render only; they do not execute work.
- Workers communicate by completing typed work orders and writing artifacts/events.
- Every side effect is approval-gated and scope-checked.
- Every external request has idempotency metadata.
- Bounded turns and max rounds are enforced by orchestrator state, not prompt convention.
- Agent identity is registry data; process identity is capacity.
- Retired agents remain in history for replay.

## Final verdict

Blackboard-only is enough for the first real Zeus OS implementation, provided it is a typed durable workflow blackboard rather than an unstructured shared transcript. Full A2A is overkill as an internal bus today, but A2A-shaped schema and projection should be designed in from the start. The best path is a blackboard-centered core with a thin A2A adapter at the boundary, added incrementally and constrained by the same queue, approval, replay, artifact, and registry rules as Discord and CLI.
