from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .config import PipelineConfig, load_pipeline_config


PHASES = ("created", "interviewing", "seeded", "running", "evaluated", "evolved", "completed", "blocked", "failed")
AMBIGUITY_THRESHOLD = 0.2
INTERVIEW_DIMENSIONS = ("scope", "acceptance", "constraint", "executor", "permission")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|passwd|token|authorization)\b\s*[:=]\s*([^\s,;]+)"
)


class DiscordThreadClient(Protocol):
    def create_thread(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create a Discord thread and return thread metadata."""


class PendingDiscordThreadClient:
    """Safe adapter that records the requested thread creation as a handoff artifact."""

    def create_thread(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "platform": "discord",
            "parent_channel_id": request.get("parent_channel_id"),
            "channel_id": request.get("parent_channel_id"),
            "thread_id": None,
            "thread_name": request.get("thread_name"),
            "message_id": request.get("message_id"),
            "jump_url": None,
            "url": None,
            "state": "pending",
            "handoff": {
                "action": "discord.create_thread",
                "contract_version": 1,
                "requires_explicit_operator_approval": True,
                "idempotency_key": request.get("run_id"),
                "request": request,
            },
        }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _redact_text(value: str) -> str:
    return SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def _validate_run_id(run_id: str) -> None:
    if not run_id or not RUN_ID_RE.fullmatch(run_id) or ".." in run_id:
        raise ValueError(f"Invalid houroboros run_id: {run_id!r}")


def _run_id(goal: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{created_at}\n{goal}".encode("utf-8")).hexdigest()[:12]
    return f"hooo-{created_at[:10].replace('-', '')}-{digest}"


def _ensure_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS houroboros_runs (
                run_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                phase TEXT NOT NULL,
                origin_platform TEXT,
                origin_channel_id TEXT,
                origin_thread_id TEXT,
                seed_version INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def load_run(db_path: Path, run_id: str) -> dict[str, Any]:
    _ensure_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM houroboros_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown houroboros run: {run_id}")
    return dict(row)


@dataclass(frozen=True)
class HouroborosWorkflow:
    workspace_root: Path
    db_path: Path

    @classmethod
    def from_config(cls, config: PipelineConfig) -> "HouroborosWorkflow":
        return cls(workspace_root=config.workspace_root, db_path=config.workspace_root / "state" / "houroboros.db")

    @classmethod
    def from_config_path(cls, config_path: Path | str) -> "HouroborosWorkflow":
        return cls.from_config(load_pipeline_config(Path(config_path)))

    def start(
        self,
        goal: str,
        origin_platform: str = "",
        origin_channel_id: str = "",
        origin_thread_id: str = "",
        *,
        auto_open_thread: bool = False,
        thread_name: str = "",
        origin_message_id: str = "",
        thread_client: DiscordThreadClient | None = None,
    ) -> dict[str, Any]:
        goal = _redact_text(goal)
        run_id, _created_at = self._reserve_run_row(
            goal=goal,
            origin_platform=origin_platform,
            origin_channel_id=origin_channel_id,
            origin_thread_id=origin_thread_id,
        )
        thread = self._initial_thread_metadata(
            run_id=run_id,
            goal=goal,
            origin_platform=origin_platform,
            origin_channel_id=origin_channel_id,
            origin_thread_id=origin_thread_id,
            origin_message_id=origin_message_id,
            auto_open_thread=auto_open_thread,
            thread_name=thread_name,
            thread_client=thread_client,
        )
        resolved_thread_id = str(thread.get("thread_id") or (origin_thread_id if not auto_open_thread else "") or "")
        if resolved_thread_id != (origin_thread_id or ""):
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE houroboros_runs SET origin_thread_id = ?, updated_at = ? WHERE run_id = ?", (resolved_thread_id or None, _now(), run_id))
                conn.commit()
        self._write_origin(run_id, origin_platform, origin_channel_id, resolved_thread_id, thread)
        self._write_interview_state(run_id, self._initial_interview_state(run_id, goal))
        self._append_interview_card(run_id, "interview.started")
        return self.status(run_id)

    def _reserve_run_row(
        self,
        *,
        goal: str,
        origin_platform: str,
        origin_channel_id: str,
        origin_thread_id: str,
    ) -> tuple[str, str]:
        """Reserve the DB row before any adapter side effect.

        The first run_id stays deterministic; bounded nonce retries avoid collisions
        when the same goal starts within the same timestamp bucket.
        """
        _ensure_schema(self.db_path)
        created_at = _now()
        last_error: sqlite3.IntegrityError | None = None
        for nonce in range(100):
            run_id = _run_id(goal, created_at) if nonce == 0 else _run_id(f"{goal}\nnonce:{nonce}", created_at)
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO houroboros_runs (
                            run_id, goal, phase, origin_platform, origin_channel_id, origin_thread_id,
                            seed_version, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (run_id, goal, "interviewing", origin_platform or None, origin_channel_id or None, origin_thread_id or None, 0, created_at, created_at),
                    )
                    conn.commit()
                return run_id, created_at
            except sqlite3.IntegrityError as exc:
                last_error = exc
        raise sqlite3.IntegrityError(f"Unable to reserve unique houroboros run_id after retries: {last_error}")

    def turn(self, run_id: str, message: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        message = _redact_text(message)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"created", "interviewing"}, "record interview turn")
        self._append_jsonl(run_id, "interview.jsonl", {"at": _now(), "role": "user", "message": message})
        self._update_interview_state_from_turn(run_id, run["goal"], message)
        self._append_interview_card(run_id, "interview.updated")
        if run["phase"] == "created":
            self._set_phase(run_id, "interviewing")
        return self.status(run_id)

    def seed(self, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"created", "interviewing", "seeded"}, "seed")
        seed_json = self._artifact_path(run_id, "seed.json")
        seed_md = self._artifact_path(run_id, "seed.md")
        if seed_json.exists() and seed_md.exists():
            result = self.status(run_id)
            result["created"] = False
            result["seed_version"] = int(run["seed_version"] or 1)
            return result

        interview = self._read_interview(run_id)
        interview_state = self._load_interview_state(run_id, run["goal"])
        if float(interview_state.get("ambiguity_score", 1.0)) > AMBIGUITY_THRESHOLD:
            raise ValueError(
                f"Cannot seed {run_id}: ambiguity {interview_state['ambiguity_score']} is above threshold {AMBIGUITY_THRESHOLD}; continue the Discord interview first"
            )
        acceptance = self._acceptance_from_interview(interview)
        seed = {
            "run_id": run_id,
            "version": 1,
            "goal": run["goal"],
            "created_at": _now(),
            "ambiguity_score": interview_state["ambiguity_score"],
            "interview_gate": {"threshold": AMBIGUITY_THRESHOLD, "passed": True},
            "decisions": interview_state.get("decisions", {}),
            "acceptance_criteria": acceptance,
            "constraints": [
                "Jarvis workspace artifacts only",
                "No Hermes source/config mutation",
                "No external service calls",
                "Seed v1 is immutable; evolve writes proposals instead of hidden mutation",
            ],
        }
        self._write_json(run_id, "seed.json", seed)
        seed_md.write_text(self._seed_markdown(seed), encoding="utf-8")
        self._set_phase(run_id, "seeded", seed_version=1)
        result = self.status(run_id)
        result["created"] = True
        result["seed_version"] = 1
        return result

    def run(self, run_id: str, executor: str = "") -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"seeded", "running"}, "run")
        seed = self._load_seed(run_id)
        executor_name = executor or str(seed.get("decisions", {}).get("executor") or "deterministic-placeholder")
        if executor_name in {"claude-code", "claude_code"}:
            self._write_claude_code_handoff(run_id, seed)
            mode = "claude_code_handoff"
            limitation = "Claude Code execution is deferred to an explicit worker; this command only writes the handoff contract"
        else:
            mode = "deterministic placeholder"
            limitation = "placeholder evidence is synthetic and only suitable for dry-run workflow validation"
        lines = [
            "# Houroboros Execution Log",
            "",
            f"- Run ID: {run_id}",
            f"- Recorded at: {_now()}",
            f"- Mode: {mode}",
            f"- Limitation: {limitation}",
            "- External mutations: none",
            "",
            "## Evidence",
        ]
        for criterion in seed["acceptance_criteria"]:
            lines.append(f"- PASS evidence recorded for: {criterion}")
        self._artifact_path(run_id, "execution_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._set_phase(run_id, "running")
        return self.status(run_id)

    def evaluate(self, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"running", "evaluated", "blocked"}, "evaluate")
        seed = self._load_seed(run_id)
        execution_log = self._artifact_path(run_id, "execution_log.md").read_text(encoding="utf-8") if self._artifact_path(run_id, "execution_log.md").exists() else ""
        checks = []
        for criterion in seed["acceptance_criteria"]:
            checks.append({"criterion": criterion, "passed": criterion in execution_log})
        passed = all(check["passed"] for check in checks)
        evaluation = [
            "# Houroboros Evaluation",
            "",
            f"- Run ID: {run_id}",
            f"- Evaluated at: {_now()}",
            "- Mode: placeholder substring match against execution_log.md",
            "- Limitation: this is a dry-run gate, not proof of real-world task completion",
            f"- Passed: {passed}",
            "",
            "## Acceptance Criteria",
        ]
        for check in checks:
            mark = "PASS" if check["passed"] else "FAIL"
            evaluation.append(f"- {mark}: {check['criterion']}")
        self._artifact_path(run_id, "evaluation.md").write_text("\n".join(evaluation) + "\n", encoding="utf-8")
        self._artifact_path(run_id, "drift.md").write_text(self._drift_markdown(run_id, passed, checks), encoding="utf-8")
        self._set_phase(run_id, "evaluated" if passed else "blocked")
        result = self.status(run_id)
        result["passed"] = passed
        return result

    def evolve(self, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"evaluated", "evolved"}, "evolve")
        seed = self._load_seed(run_id)
        text = "\n".join([
            "# Houroboros Evolution Proposal",
            "",
            f"- Run ID: {run_id}",
            f"- Proposed at: {_now()}",
            f"- Based on immutable seed: v{seed['version']}",
            "- Mutation policy: do not rewrite seed.json or seed.md",
            "",
            "## Proposal",
            f"Continue the Ralph-style loop from phase `{run['phase']}` using evaluation and drift artifacts as input.",
        ])
        self._artifact_path(run_id, "evolution.md").write_text(text + "\n", encoding="utf-8")
        self._set_phase(run_id, "evolved")
        return self.status(run_id)

    def status(self, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        run_dir = self._run_dir(run_id)
        artifacts = sorted(str(path.relative_to(self.workspace_root)) for path in run_dir.glob("*")) if run_dir.exists() else []
        drift_path = self._artifact_path(run_id, "drift.md")
        return {
            "run_id": run_id,
            "goal": run["goal"],
            "phase": run["phase"],
            "execution_mode": self._execution_mode(run_id),
            "evaluation_mode": "placeholder_substring_match",
            "seed_version": run["seed_version"],
            "interview_state": self._load_interview_state(run_id, run["goal"]),
            "origin": self._origin_metadata(run_id, run),
            "warnings": self._status_warnings(run_id, run),
            "artifacts": artifacts,
            "latest_drift": drift_path.read_text(encoding="utf-8") if drift_path.exists() else "",
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
        }

    def export(self, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        return {
            "run": run,
            "status": self.status(run_id),
            "interview": self._read_interview(run_id),
            "seed": self._load_seed(run_id) if self._artifact_path(run_id, "seed.json").exists() else None,
            "artifacts": self._artifact_texts(run_id),
        }

    def mark_thread_created(
        self,
        run_id: str,
        *,
        thread_id: str,
        thread_name: str = "",
        message_id: str = "",
        jump_url: str = "",
        url: str = "",
    ) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        origin = self._origin_metadata(run_id, run)
        thread = dict(origin.get("thread") or {})
        handoff_path = self._artifact_path(run_id, "thread_handoff.json")
        if thread.get("state") not in {"pending", "error"} and not handoff_path.exists():
            raise ValueError(f"Cannot mark thread for {run_id}: no pending Discord thread handoff exists")
        thread.update(
            {
                "platform": "discord",
                "parent_channel_id": origin.get("channel_id"),
                "channel_id": origin.get("channel_id"),
                "thread_id": thread_id,
                "thread_name": thread_name or thread.get("thread_name"),
                "message_id": message_id or thread.get("message_id"),
                "jump_url": jump_url or thread.get("jump_url"),
                "url": url or thread.get("url"),
                "state": "created",
                "updated_at": _now(),
            }
        )
        self._write_origin(run_id, str(origin.get("platform") or "discord"), str(origin.get("channel_id") or ""), thread_id, thread)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE houroboros_runs SET origin_thread_id = ?, updated_at = ? WHERE run_id = ?", (thread_id, _now(), run_id))
            conn.commit()
        return self.status(run_id)

    def _set_phase(self, run_id: str, phase: str, seed_version: int | None = None) -> None:
        if phase not in PHASES:
            raise ValueError(f"Unknown houroboros phase: {phase}")
        updated_at = _now()
        with sqlite3.connect(self.db_path) as conn:
            if seed_version is None:
                conn.execute("UPDATE houroboros_runs SET phase = ?, updated_at = ? WHERE run_id = ?", (phase, updated_at, run_id))
            else:
                conn.execute("UPDATE houroboros_runs SET phase = ?, seed_version = ?, updated_at = ? WHERE run_id = ?", (phase, seed_version, updated_at, run_id))
            conn.commit()

    def _require_phase(self, run_id: str, phase: str, allowed: set[str], action: str) -> None:
        if phase not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(f"Invalid houroboros transition for {run_id}: cannot {action} from phase {phase}; expected one of: {allowed_text}")

    def _initial_thread_metadata(
        self,
        *,
        run_id: str,
        goal: str,
        origin_platform: str,
        origin_channel_id: str,
        origin_thread_id: str,
        origin_message_id: str,
        auto_open_thread: bool,
        thread_name: str,
        thread_client: DiscordThreadClient | None,
    ) -> dict[str, Any]:
        if origin_platform != "discord" and not auto_open_thread:
            return {"state": "not_requested"}
        name = thread_name or f"hooo {run_id}"
        if origin_thread_id and not auto_open_thread:
            return {
                "platform": "discord",
                "parent_channel_id": origin_channel_id or None,
                "channel_id": origin_channel_id or None,
                "thread_id": origin_thread_id,
                "thread_name": name,
                "message_id": origin_message_id or None,
                "jump_url": None,
                "url": None,
                "state": "created",
            }
        if not auto_open_thread:
            return {
                "platform": "discord" if origin_platform == "discord" else origin_platform or None,
                "parent_channel_id": origin_channel_id or None,
                "channel_id": origin_channel_id or None,
                "thread_id": None,
                "thread_name": name,
                "message_id": origin_message_id or None,
                "jump_url": None,
                "url": None,
                "state": "not_requested",
            }
        request = {
            "platform": "discord",
            "run_id": run_id,
            "goal": goal,
            "parent_channel_id": origin_channel_id or None,
            "source_origin_thread_id": origin_thread_id or None,
            "reuse_current_thread": False,
            "message_id": origin_message_id or None,
            "thread_name": name,
        }
        client = thread_client or PendingDiscordThreadClient()
        try:
            metadata = dict(client.create_thread(request))
        except Exception as exc:  # adapter boundary: capture error as artifact, do not hide it
            metadata = {
                "platform": "discord",
                "parent_channel_id": origin_channel_id or None,
                "channel_id": origin_channel_id or None,
                "thread_id": None,
                "thread_name": name,
                "message_id": origin_message_id or None,
                "jump_url": None,
                "url": None,
                "state": "error",
                "error": str(exc),
                "handoff": {
                    "action": "discord.create_thread",
                    "contract_version": 1,
                    "requires_explicit_operator_approval": True,
                    "idempotency_key": request.get("run_id"),
                    "request": request,
                },
            }
        metadata.setdefault("platform", "discord")
        metadata.setdefault("parent_channel_id", origin_channel_id or None)
        metadata.setdefault("channel_id", metadata.get("parent_channel_id"))
        metadata.setdefault("thread_id", None)
        metadata.setdefault("thread_name", name)
        metadata.setdefault("message_id", origin_message_id or None)
        metadata.setdefault("jump_url", None)
        metadata.setdefault("url", None)
        metadata.setdefault("state", "created" if metadata.get("thread_id") else "pending")
        return metadata

    def _write_origin(self, run_id: str, platform: str, channel_id: str, thread_id: str, thread: dict[str, Any]) -> None:
        self._write_json(
            run_id,
            "origin.json",
            {
                "platform": platform or None,
                "channel_id": channel_id or None,
                "thread_id": thread_id or None,
                "thread": thread,
            },
        )
        if thread.get("handoff"):
            self._write_json(run_id, "thread_handoff.json", thread["handoff"])

    def _origin_metadata(self, run_id: str, run: dict[str, Any]) -> dict[str, Any]:
        origin_path = self._artifact_path(run_id, "origin.json")
        if origin_path.exists():
            origin = json.loads(origin_path.read_text(encoding="utf-8"))
        else:
            origin = {}
        origin.setdefault("platform", run["origin_platform"])
        origin.setdefault("channel_id", run["origin_channel_id"])
        origin.setdefault("thread_id", run["origin_thread_id"])
        origin.setdefault("thread", {"state": "unknown", "thread_id": run["origin_thread_id"]})
        return origin

    def _run_dir(self, run_id: str) -> Path:
        _validate_run_id(run_id)
        return self.workspace_root / "data" / "houroboros" / run_id

    def _artifact_path(self, run_id: str, filename: str) -> Path:
        path = self._run_dir(run_id) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, run_id: str, filename: str, value: Any) -> None:
        self._artifact_path(run_id, filename).write_text(_json_dumps(value) + "\n", encoding="utf-8")

    def _append_jsonl(self, run_id: str, filename: str, value: Any) -> None:
        path = self._artifact_path(run_id, filename)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")

    def _read_jsonl(self, run_id: str, filename: str) -> list[dict[str, Any]]:
        path = self._artifact_path(run_id, filename)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _next_card_revision(self, run_id: str) -> int:
        return len(self._read_jsonl(run_id, "discord_cards.jsonl")) + 1

    def _latest_card_revision(self, run_id: str) -> int:
        return len(self._read_jsonl(run_id, "discord_cards.jsonl"))

    def _read_interview(self, run_id: str) -> list[dict[str, Any]]:
        path = self._artifact_path(run_id, "interview.jsonl")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _load_seed(self, run_id: str) -> dict[str, Any]:
        seed_path = self._artifact_path(run_id, "seed.json")
        if not seed_path.exists():
            raise FileNotFoundError(f"Seed does not exist for run {run_id}; run `houroboros seed` first")
        return json.loads(seed_path.read_text(encoding="utf-8"))

    def _artifact_texts(self, run_id: str) -> dict[str, str]:
        texts = {}
        for path in sorted(self._run_dir(run_id).glob("*")):
            if path.is_file() and path.suffix in {".md", ".json", ".jsonl"}:
                texts[path.name] = path.read_text(encoding="utf-8")
        return texts


    def _initial_interview_state(self, run_id: str, goal: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "goal": goal,
            "threshold": AMBIGUITY_THRESHOLD,
            "ambiguity_score": 1.0,
            "seed_ready": False,
            "resolved": [],
            "unresolved": list(INTERVIEW_DIMENSIONS),
            "decisions": {},
            "decision_log": [],
            "updated_at": _now(),
        }

    def _load_interview_state(self, run_id: str, goal: str) -> dict[str, Any]:
        path = self._artifact_path(run_id, "interview_state.json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return self._initial_interview_state(run_id, goal)

    def _write_interview_state(self, run_id: str, state: dict[str, Any]) -> None:
        self._write_json(run_id, "interview_state.json", state)

    def _update_interview_state_from_turn(self, run_id: str, goal: str, message: str) -> None:
        state = self._load_interview_state(run_id, goal)
        resolved = set(state.get("resolved", []))
        decisions = dict(state.get("decisions") or {})
        lowered = message.strip().lower()
        freeform = True
        for key in INTERVIEW_DIMENSIONS:
            if lowered.startswith(f"{key}:"):
                resolved.add(key)
                value = message.split(":", 1)[1].strip()
                decisions[key] = value
                freeform = False
        if lowered.startswith("executor:"):
            raw_executor = message.split(":", 1)[1].strip().split(",", 1)[0].strip().lower().replace(" ", "-")
            executor = "claude-code" if "claude-code" in raw_executor else raw_executor
            decisions["executor"] = executor
        if freeform and message.strip():
            decisions.setdefault("notes", []).append(message.strip())
        unresolved = [key for key in INTERVIEW_DIMENSIONS if key not in resolved]
        score = round(len(unresolved) / len(INTERVIEW_DIMENSIONS), 2)
        state.update({
            "ambiguity_score": score,
            "seed_ready": score <= AMBIGUITY_THRESHOLD,
            "resolved": [key for key in INTERVIEW_DIMENSIONS if key in resolved],
            "unresolved": unresolved,
            "decisions": decisions,
            "updated_at": _now(),
        })
        state.setdefault("decision_log", []).append({"at": _now(), "message": message, "resolved": state["resolved"], "ambiguity_score": score})
        self._write_interview_state(run_id, state)

    def _append_interview_card(self, run_id: str, event: str) -> dict[str, Any]:
        run = load_run(self.db_path, run_id)
        state = self._load_interview_state(run_id, run["goal"])
        origin = self._origin_metadata(run_id, run)
        revision = self._next_card_revision(run_id)
        card_id = f"hooo-interview:{run_id}"
        target_thread_id = origin.get("thread_id") or (origin.get("thread") or {}).get("thread_id")
        components = self._interview_components(run_id, revision, bool(state["seed_ready"]))
        card = {
            "action": "discord.interaction_message",
            "contract_version": 2,
            "event": event,
            "run_id": run_id,
            "card_id": card_id,
            "card_revision": revision,
            "idempotency_key": f"hooo:discord-card:{run_id}:{revision}",
            "created_at": _now(),
            "render_mode": "update_existing",
            "render_state": "pending",
            "target": {
                "platform": origin.get("platform") or "discord",
                "channel_id": origin.get("channel_id"),
                "thread_id": target_thread_id,
                "parent_channel_id": (origin.get("thread") or {}).get("parent_channel_id") or origin.get("channel_id"),
                "origin_message_id": (origin.get("thread") or {}).get("message_id"),
            },
            "interaction_policy": {
                "requires_explicit_operator_approval": True,
                "allowed_actions": ["continue_interview", "propose_seed", "cancel"],
                "reject_stale_revision": True,
                "validate_run_id": True,
                "validate_channel_thread": True,
                "do_not_bypass_ambiguity_gate": True,
                "side_effect_class": "jarvis_workspace_write_only",
            },
            "card": {
                "kind": "interview",
                "title": "HOOO Interview",
                "goal": run["goal"],
                "goal_summary": self._display_text(run["goal"]),
                "ambiguity_score": state["ambiguity_score"],
                "threshold": AMBIGUITY_THRESHOLD,
                "seed_ready": state["seed_ready"],
                "unresolved": state["unresolved"],
                "decisions": self._display_decisions(state.get("decisions", {})),
                "buttons": [component["action"] for component in components],
                "components": components,
            },
        }
        self._append_jsonl(run_id, "discord_cards.jsonl", card)
        return card

    def _interview_components(self, run_id: str, revision: int, seed_ready: bool) -> list[dict[str, Any]]:
        specs = [
            ("continue_interview", "Continue Interview", "secondary", False, False, ["created", "interviewing"]),
            ("propose_seed", "Propose Seed", "primary", not seed_ready, True, ["created", "interviewing", "seeded"]),
            ("cancel", "Cancel", "danger", False, False, ["created", "interviewing"]),
        ]
        components = []
        for action, label, style, disabled, requires_seed_ready, allowed_phase in specs:
            custom_id = f"hooo:v2:{action}:{run_id}:r{revision}"
            if len(custom_id) > 100:
                raise ValueError(f"Discord custom_id too long for {run_id}: {action}")
            components.append({
                "type": "button",
                "action": action,
                "label": label,
                "style": style,
                "disabled": disabled,
                "custom_id": custom_id,
                "requires_seed_ready": requires_seed_ready,
                "requires_explicit_operator_approval": True,
                "allowed_phase": allowed_phase,
            })
        return components

    def _display_text(self, value: str, limit: int = 180) -> str:
        text = _redact_text(str(value)).replace("\n", " ").strip()
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _display_decisions(self, decisions: dict[str, Any]) -> dict[str, Any]:
        display: dict[str, Any] = {}
        for key, value in decisions.items():
            if isinstance(value, list):
                display[key] = [self._display_text(str(item)) for item in value]
            else:
                display[key] = self._display_text(str(value))
        return display

    def _parse_interaction_custom_id(self, custom_id: str) -> tuple[str, str, int]:
        match = re.fullmatch(r"hooo:v2:([a-z_]+):([A-Za-z0-9_.-]+):r([0-9]+)", custom_id or "")
        if not match:
            raise ValueError("Invalid HOOO Discord interaction custom_id")
        action, run_id, revision = match.group(1), match.group(2), int(match.group(3))
        _validate_run_id(run_id)
        return action, run_id, revision

    def handle_interaction(
        self,
        run_id: str,
        action: str = "",
        *,
        card_revision: int | None = None,
        custom_id: str = "",
        origin_channel_id: str = "",
        origin_thread_id: str = "",
        actor_id: str = "",
    ) -> dict[str, Any]:
        _validate_run_id(run_id)
        if custom_id:
            parsed_action, parsed_run_id, parsed_revision = self._parse_interaction_custom_id(custom_id)
            if parsed_run_id != run_id:
                raise ValueError("Discord interaction run_id mismatch")
            if action and action != parsed_action:
                raise ValueError("Discord interaction action/custom_id mismatch")
            action = parsed_action
            card_revision = parsed_revision
        if action not in {"continue_interview", "propose_seed", "cancel"}:
            raise ValueError(f"Unknown HOOO interaction action: {action}")
        if card_revision is None:
            raise ValueError("Discord interaction card_revision is required")
        run = load_run(self.db_path, run_id)
        allowed_by_action = {
            "continue_interview": {"created", "interviewing"},
            "propose_seed": {"created", "interviewing", "seeded"},
            "cancel": {"created", "interviewing"},
        }
        if run["phase"] not in allowed_by_action[action]:
            allowed_text = ", ".join(sorted(allowed_by_action[action]))
            raise ValueError(f"Invalid HOOO interaction {action} from phase {run['phase']}; expected one of: {allowed_text}")
        origin = self._origin_metadata(run_id, run)
        expected_channel_id = str(origin.get("channel_id") or "")
        if expected_channel_id and origin_channel_id != expected_channel_id:
            raise ValueError("Discord interaction channel mismatch")
        expected_thread_id = str(origin.get("thread_id") or (origin.get("thread") or {}).get("thread_id") or "")
        if expected_thread_id:
            if origin_thread_id != expected_thread_id:
                raise ValueError("Discord interaction thread mismatch")
        elif origin_thread_id:
            raise ValueError("Discord interaction thread mismatch")
        latest_revision = self._latest_card_revision(run_id)
        if card_revision != latest_revision:
            raise ValueError(f"Stale or unknown HOOO interaction card revision {card_revision}; latest is {latest_revision}")

        self._append_jsonl(run_id, "interaction_log.jsonl", {
            "at": _now(),
            "action": action,
            "card_revision": card_revision,
            "actor_id": actor_id or None,
            "origin_channel_id": origin_channel_id or None,
            "origin_thread_id": origin_thread_id or None,
            "side_effects": "jarvis_workspace_write_only",
        })
        if action == "continue_interview":
            card = self._append_interview_card(run_id, "interview.continue_requested")
            result = self.status(run_id)
            result["interaction"] = {"action": action, "handled": True, "card_revision": card["card_revision"], "next_unresolved": result["interview_state"].get("unresolved", [])}
            return result
        if action == "propose_seed":
            result = self.seed(run_id)
            result["interaction"] = {"action": action, "handled": True, "gate_rechecked": True}
            return result
        self._set_phase(run_id, "blocked")
        self._append_interview_card(run_id, "interview.cancelled")
        result = self.status(run_id)
        result["interaction"] = {"action": action, "handled": True, "terminal_phase": "blocked"}
        return result

    def _write_claude_code_handoff(self, run_id: str, seed: dict[str, Any]) -> None:
        command = "claude -p 'Execute this HOOO seed from stdin; implement only Jarvis-owned changes, then run tests' --max-turns 10 --allowedTools 'Read,Edit,Write,Bash(PYTHONPATH=src pytest *),Bash(python -m compileall *)'"
        self._write_json(run_id, "claude_code_handoff.json", {
            "action": "claude-code.execute_seed",
            "contract_version": 1,
            "run_id": run_id,
            "seed_version": seed["version"],
            "side_effects": "deferred",
            "requires_explicit_operator_approval": True,
            "workspace_root": str(self.workspace_root),
            "recommended_command": command,
            "seed": seed,
        })

    def _execution_mode(self, run_id: str) -> str:
        if self._artifact_path(run_id, "claude_code_handoff.json").exists():
            return "claude_code_handoff"
        return "deterministic_placeholder"

    def _status_warnings(self, run_id: str, run: dict[str, Any]) -> list[str]:
        warnings = []
        origin = self._origin_metadata(run_id, run)
        thread = origin.get("thread") or {}
        if thread.get("state") == "error":
            warnings.append(f"discord thread handoff failed: {thread.get('error', 'unknown error')}")
        if self._execution_mode(run_id) == "deterministic_placeholder" and run.get("phase") in {"running", "evaluated", "evolved"}:
            warnings.append("execution evidence is deterministic dry-run evidence, not real-world task completion proof")
        return warnings

    def _acceptance_from_interview(self, interview: list[dict[str, Any]]) -> list[str]:
        criteria = []
        for item in interview:
            message = str(item.get("message", "")).strip()
            if message:
                criteria.append(message)
        return criteria or ["Seed created for the stated goal", "Execution log records no external mutations", "Evaluation compares seed criteria to evidence"]

    def _seed_markdown(self, seed: dict[str, Any]) -> str:
        lines = ["# Houroboros Seed v1", "", f"Goal: {seed['goal']}", "", "## Acceptance Criteria"]
        lines.extend(f"- {criterion}" for criterion in seed["acceptance_criteria"])
        lines.extend(["", "## Constraints"])
        lines.extend(f"- {constraint}" for constraint in seed["constraints"])
        return "\n".join(lines) + "\n"

    def _drift_markdown(self, run_id: str, passed: bool, checks: list[dict[str, Any]]) -> str:
        failing = [check["criterion"] for check in checks if not check["passed"]]
        lines = ["# Houroboros Drift", "", f"- Run ID: {run_id}", f"- Drift detected: {not passed}"]
        if failing:
            lines.extend(["", "## Missing Evidence"])
            lines.extend(f"- {criterion}" for criterion in failing)
        else:
            lines.extend(["", "No acceptance drift detected against recorded execution evidence."])
        return "\n".join(lines) + "\n"
