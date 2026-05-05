# Zeus OS Operator Guide

This guide covers operational concerns for running Zeus OS in production.

## Architecture

- **Hot control plane**: SQLite WAL at `state/zeus_os.db`
- **Artifact layer**: Filesystem under `data/zeus/tasks/<task_id>/`
- **Projections**: Discord boardroom cards, A2A mappings, analytics exports
- **No external services required** for deterministic MVP

## Invariants

1. Hermes source is untouched. Integration lives in `plugins/hermes_zeus_gateway/`.
2. SQLite + artifacts are canonical. Projections are read-only views.
3. One Discord bot identity for MVP. Personas are `agent_cards` rows.
4. Every agent exchange is bounded by `task_id`, agenda, max rounds, and budget.
5. Orchestrator decomposes and gates. Workers execute only through approved adapters.
6. No secrets or private reasoning persist. Only summaries, evidence, and decisions.
7. Deterministic first. Fake/stub workers precede live LLM or Discord adapters.

## Database

### WAL Mode

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

WAL mode allows readers to proceed during writes. Do not switch to DELETE or TRUNCATE mode.

### Backup

```bash
cp state/zeus_os.db state/zeus_os.db.backup
```

WAL checkpoint before copying:

```sql
PRAGMA wal_checkpoint(TRUNCATE);
```

## Approval Gates

Required approvals include:

- `repo_write`: Any code change
- `local_artifact_write`: Non-task artifact writes
- `external_post`: Discord, mail, calendar writes
- `credential_access`: API keys, tokens
- `discord_config`: Bot configuration
- `gateway_systemd`: Service management
- `cost_budget`: LLM/image generation costs
- `image_generation`: Live image generation (gated)
- `public_publication`: Public posts (separate from image generation)
- `destructive_action`: Deletes, drops, overwrites
- `human_input`: Explicit human feedback

Each approval has `scope_json`, `scope_hash`, `target_revision`, and `expires_at`. Stale or mismatched approvals are rejected.

## Queue Operations

### State Machine

```
ready -> leased -> acked
ready -> leased -> ready (backoff)
ready -> leased -> dead
ready/leased -> canceled
```

### Recovery

Expired leases (lease_expires_at < now) are recovered by `zeus queue recover` or the doctor check. Items exceeding `max_attempts` go to dead-letter.

## Worker Model

Workers claim from `worker.<kind>` topics. Claim atomically leases both the queue row and the referenced `work_orders` row.

Deterministic workers (MVP) do not call LLMs. They write artifacts, update state, and ack.

## Artifact Security

- Root: `data/zeus/tasks/<task_id>/`
- Relative URIs only in DB
- Path traversal rejected: no `..`, absolute paths, or symlink escapes
- Atomic writes: temp file, fsync, rename
- Hash verification on registration and reconciliation

## Redaction

Safety module scans for:

- Discord bot tokens
- Bearer/API keys
- Private keys
- `chain_of_thought`, `reasoning_trace` fields

Redaction runs before DB persistence, projection, and export.

## Boardroom Rules

- `max_rounds` is hard-enforced
- `agenda_items.turn_budget_json` limits turns per item
- Agent-proposed spawned tasks require policy/user approval
- Final arbiter can close or escalate
- No recursive unbounded chatter

## Discord Integration (Future)

Stop and ask Jinwang for bot token only after:

1. CLI-only deterministic Zeus OS passes tests
2. Discord plugin dry-run tests pass without gateway restart
3. Operator guide lists exact scopes/permissions
4. No secrets in repo/artifacts

Minimum permissions: send messages, read history, create threads, slash commands. Avoid Administrator.

## Systemd Templates

Templates exist in `scripts/` but are not installed automatically. Manual installation requires explicit scoped approval.

## Monitoring

Run `zeus doctor` periodically. Check:

- DB schema version
- WAL and foreign keys
- Artifact integrity
- Expired leases
- Stale workers
- Dead letters
- Pending approvals
- Projection lag
- Secret findings

## Rollback

Before any live action:

1. Capture current service status
2. Document rollback command
3. Require scoped human approval
4. Perform health/smoke after action
