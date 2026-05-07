# Zeus OS Usage Guide

Zeus OS is the ZeusOS-owned Agent OS control plane. It provides deterministic, stdlib-only multi-agent orchestration with SQLite WAL as the canonical store.

## Quick Start

### Initialize Zeus OS

```bash
python -m zeus_os.cli zeus init
```

This creates the SQLite schema with WAL mode, foreign keys, and seeds 13 default agent cards including Painter.

### Submit a Task

```bash
python -m zeus_os.cli zeus task submit --title "Implement feature X" --goal "Add user authentication"
```

### Check Task Status

```bash
python -m zeus_os.cli zeus task status <task_id>
```

### Replay Task Events

```bash
python -m zeus_os.cli zeus task replay <task_id>
```

### Export Task to JSONL

```bash
python -m zeus_os.cli zeus task export <task_id> --output data/exports/task.jsonl
```

## Agent Management

### List Agents

```bash
python -m zeus_os.cli zeus agent list
```

### Show Agent Details

```bash
python -m zeus_os.cli zeus agent show painter
```

## Boardroom Sessions

### Create a Session

```bash
python -m zeus_os.cli zeus boardroom create --title "Design review"
```

### Advance Rounds

```bash
python -m zeus_os.cli zeus boardroom advance <session_id>
```

Sessions enforce `max_rounds`. When exceeded, the session auto-closes.

## Queue and Workers

### List Queue State

```bash
python -m zeus_os.cli zeus queue list
```

### Recover Expired Leases

```bash
python -m zeus_os.cli zeus queue recover
```

### Run a Deterministic Worker

```bash
python -m zeus_os.cli zeus worker run --kind deterministic --once
```

## Painter Workflow

### Run Painter (Deterministic Fake Images)

```bash
python -m zeus_os.cli zeus painter run <task_id> --purpose "Blog header" --prompt "A serene mountain landscape" --style "Minimalist"
```

This creates `brief.md`, `prompt.md`, and `image.json` artifacts. Live image generation is gated behind approval.

## A2A Projection

### View A2A Task Projection

```bash
python -m zeus_os.cli zeus a2a task <task_id>
```

### View A2A Agent Card

```bash
python -m zeus_os.cli zeus a2a agent <agent_id>
```

## Health Checks

### Run Doctor

```bash
python -m zeus_os.cli zeus doctor
```

Doctor reports: DB health, WAL mode, artifact integrity, queue state, expired leases, stale workers, dead letters, pending approvals, projection lag, and secret scans.

## Data Model

Canonical store: `state/zeus_os.db` (SQLite WAL).

Artifact root: `data/zeus/tasks/<task_id>/`.

Key entities: tasks, work_orders, messages, boardroom_sessions, approvals, task_events (event sourcing), bus_queue, artifacts.
