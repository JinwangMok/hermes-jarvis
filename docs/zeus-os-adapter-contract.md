# ZeusOS External Adapter Contract

**Status:** draft contract  
**Date:** 2026-05-07  
**Scope:** how ZeusOS integrates Hermes, K-Skill, and other external capability providers without absorbing their repositories

## Purpose

ZeusOS should be able to use many capabilities without becoming a monolith. This document defines the boundary between ZeusOS and external systems such as Hermes, K-Skill, specialized skill repos, OpenCode workers, image generators, and future MCP/A2A services.

The rule is simple:

> ZeusOS owns orchestration, approvals, state, artifacts, and projections. External providers own their own implementation and release lifecycle.

## Adapter responsibilities

A ZeusOS adapter may own:

- capability metadata;
- input/output schema mapping;
- version compatibility checks;
- health checks and dry-run probes;
- cost/secret/side-effect classification;
- approval requirements;
- artifact registration;
- event projection into ZeusOS state;
- CLI, HTTP, MCP, A2A, or filesystem boundary calls.

A ZeusOS adapter must not:

- vendor or copy an external repository by default;
- mutate Hermes source;
- mutate an external repo without explicit approval;
- persist secrets or private reasoning;
- bypass ZeusOS approval gates for repo writes, external posts, credentials, systemd/gateway changes, or paid generation;
- treat Discord messages or generated reports as canonical state.

## Contract shape

Each adapter should be describable by a small manifest. The exact storage format may evolve, but the contract should capture at least:

```yaml
adapter_id: kskill.weather
adapter_version: 1
provider:
  name: k-skill
  source: external-repo
  upstream: https://example.invalid/k-skill.git
interface:
  kind: cli # cli | http | mcp | a2a | filesystem | hermes-plugin
  command: kskill weather
capabilities:
  - weather.lookup
inputs:
  schema_ref: schemas/weather.lookup.input.json
outputs:
  schema_ref: schemas/weather.lookup.output.json
side_effects:
  writes_repo: false
  external_post: false
  credential_access: false
  cost_budget: none
approvals:
  required: []
health:
  command: kskill doctor weather
artifacts:
  writes_under: data/zeus/tasks/<task_id>/
compatibility:
  min_version: "0.1.0"
  max_version: null
```

## Adapter classes

| Class | Example | Boundary |
|---|---|---|
| Hermes plugin adapter | `plugins/hermes_zeus_gateway/` | Hermes loads the plugin; ZeusOS owns plugin source; Hermes core remains untouched |
| CLI capability adapter | K-Skill commands | ZeusOS shells out or invokes a stable CLI contract |
| Worker adapter | OpenCode/Claude/Hermes worker | ZeusOS creates work orders and artifacts; worker execution is bounded and audited |
| Generation adapter | image/audio generation | Requires cost/safety approval and registers prompt/output artifacts |
| Projection adapter | Discord/A2A/markdown | Renders canonical state outward; projection is not canonical |

## Hermes profile adapter stance

Hermes profiles can be used as an operational adapter boundary for ZeusOS.

A profile split is useful when a capability should have separate context, sessions, skills, memory, model/cost policy, and gateway queue behavior. The first recommended split is:

| Profile | Role | Gateway stance |
|---|---|---|
| `default` / Boramae | Main human-facing orchestrator | Existing gateway remains primary |
| `jarvis` | Mail/calendar/news/report specialist | Candidate separate gateway after dry-run validation |
| `karvis` | Research/paper/Playbox specialist | Later candidate |
| `contractor` | OpenCode/Claude/Codex handoff controller | Later candidate; may be CLI/tmux-only |
| `voice` | Discord voice/STT/TTS specialist | Later candidate, especially if voice runtime diverges |

Profile adapters must observe these limits:

- profiles reduce context pollution and may reduce single-gateway queue contention;
- profiles do not provide filesystem or credential sandboxing under the same Unix user;
- real containment requires `terminal.cwd`, Docker/SSH backends, separate Unix users, or equivalent OS isolation;
- each live profile gateway requires explicit install/start/health/recovery documentation;
- gateway restarts still require Jinwang's safe-restart/recovery convention.

## Hermes-specific boundary

Hermes is the host/gateway/runtime surface, not ZeusOS core.

Allowed:
- ZeusOS-owned Hermes plugins;
- ZeusOS-owned systemd templates for local deployment;
- read-only Hermes skill search/lifecycle sidecars;
- Hermes config instructions when explicitly approved;
- gateway restart only through Jinwang's safe-restart/recovery convention.

Forbidden without explicit approval:
- editing Hermes source;
- restarting the gateway;
- changing Hermes credentials/config;
- writing to Hermes skill directories as if they were ZeusOS-owned;
- using Hermes session memory as canonical ZeusOS state.

## External repository boundary

External repos such as K-Skill, STT runtimes, or future provider-specific tools remain independently developed and tested.

ZeusOS may:
- pin a version or commit in adapter metadata;
- call the external CLI/API;
- read declared artifacts;
- write ZeusOS-side wrapper code;
- open a separate approved task to update the external repo.

ZeusOS must not:
- silently copy the external repo into ZeusOS core;
- rewrite external source while implementing a ZeusOS feature;
- make external repo internals part of the ZeusOS stable API;
- assume external credentials are available unless the adapter declares them.

## Approval mapping

| Adapter action | Required gate |
|---|---|
| Local read-only health check | none or low-risk policy |
| Write under `data/zeus/tasks/<task_id>/` | `local_artifact_write` if outside normal worker scope |
| Modify ZeusOS repo | `repo_write` |
| Modify external repo | `external_repo_write` or explicit user approval |
| Send Discord/mail/calendar | `external_post` |
| Access credentials | `credential_access` |
| Restart Hermes/systemd | `gateway_systemd` plus safe-restart recovery |
| Paid LLM/image/audio generation | `cost_budget`; generation-specific gates as needed |
| Publish public content | `public_publication` |

## Artifact contract

Adapters should write durable outputs under task-scoped artifact directories and register enough metadata for replay:

```text
data/zeus/tasks/<task_id>/<work_order_id>/
  input.json
  output.json
  result.md
  stderr.log
  provenance.json
```

`provenance.json` should include:
- adapter id/version;
- provider version or commit when available;
- command/API endpoint shape, excluding secrets;
- input hash;
- output hash;
- approval ids if any;
- timestamps;
- limitations or mock/dry-run status.

## First implementations

The first adapter work should remain documentation and dry-run oriented:

1. document the Hermes plugin boundary for `plugins/hermes_zeus_gateway/`;
2. describe K-Skill as an external CLI capability provider;
3. require all live side-effect adapters to expose dry-run mode before live mode;
4. keep adapter manifests additive until compatibility tests exist.

## Non-goals

This contract does not require:
- moving external repos into ZeusOS;
- replacing Hermes;
- creating multiple Discord bot identities;
- changing current `jinwang_jarvis` imports;
- changing active systemd units;
- moving generated wiki paths.
