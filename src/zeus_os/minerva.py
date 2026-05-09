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
from .minerva_boardroom_adapter import MinervaBoardroomAdapter
from .minerva_process import evaluate_phase_gate, phase_gate_card


PHASES = ("created", "interviewing", "seeded", "running", "evaluated", "evolved", "completed", "blocked", "failed")
AMBIGUITY_THRESHOLD = 0.2
INTERVIEW_DIMENSIONS = ("scope", "acceptance", "constraint", "executor", "permission")
PROPOSAL_OPTION_IDS = ("a", "b", "c")
INTERVIEW_DIMENSION_LABELS = {
    "scope": "Scope",
    "acceptance": "Acceptance",
    "constraint": "Constraint",
    "executor": "Executor",
    "permission": "Permission",
}
INTERVIEW_PROPOSALS = {
    "scope": (
        ("a", "ZeusOS-owned implementation", "Implement only ZeusOS-owned Minerva/Minerva runtime, gateway bridge, tests, and necessary docs for this task."),
        ("b", "Seed and plan only", "Produce a deterministic Minerva seed and implementation plan, without changing runtime behavior."),
        ("c", "Tests and contract only", "Limit work to regression tests and contract documentation; defer runtime implementation."),
    ),
    "acceptance": (
        ("a", "Tests and artifact pass", "Requested behavior is implemented, targeted tests pass, and the result artifact records verification evidence."),
        ("b", "Seed is reviewable", "A seed artifact contains explicit scope, acceptance, constraints, executor, permission, and no hidden side effects."),
        ("c", "Regression is locked", "A regression test fails on the old continue-only interview and passes with proposal buttons."),
    ),
    "constraint": (
        ("a", "ZeusOS boundary", "Modify only ZeusOS-owned repository files; do not touch Hermes source/config, secrets, systemd, cron, raw wiki, or external services."),
        ("b", "Dry-run side effects", "Avoid live Discord or gateway side effects; write local handoff/artifact evidence only."),
        ("c", "Minimal patch", "Keep the change small, test-backed, and isolated from unrelated dirty files."),
    ),
    "executor": (
        ("a", "Claude Code handoff", "claude-code"),
        ("b", "OpenCode/Sisyphus", "opencode-sisyphus"),
        ("c", "Deterministic placeholder", "deterministic-placeholder"),
    ),
    "permission": (
        ("a", "Implement and test locally", "Read/write ZeusOS-owned repo files and run local verification commands; no external side effects."),
        ("b", "Seed approval only", "Create a reviewable seed after the ambiguity gate; implementation requires separate approval."),
        ("c", "Read-only analysis", "Analyze and document the task without code changes until explicit approval."),
    ),
}
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
        raise ValueError(f"Invalid minerva run_id: {run_id!r}")


def _run_id(goal: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{created_at}\n{goal}".encode("utf-8")).hexdigest()[:12]
    return f"minerva-{created_at[:10].replace('-', '')}-{digest}"


def _ensure_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS minerva_runs (
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
        row = conn.execute("SELECT * FROM minerva_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown minerva run: {run_id}")
    return dict(row)


@dataclass(frozen=True)
class MinervaWorkflow:
    workspace_root: Path
    db_path: Path

    @classmethod
    def from_config(cls, config: PipelineConfig) -> "MinervaWorkflow":
        return cls(workspace_root=config.workspace_root, db_path=config.workspace_root / "state" / "minerva.db")

    @classmethod
    def from_config_path(cls, config_path: Path | str) -> "MinervaWorkflow":
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
                conn.execute("UPDATE minerva_runs SET origin_thread_id = ?, updated_at = ? WHERE run_id = ?", (resolved_thread_id or None, _now(), run_id))
                conn.commit()
        self._write_origin(run_id, origin_platform, origin_channel_id, resolved_thread_id, thread)
        self._write_interview_state(run_id, self._initial_interview_state(run_id, goal))
        self._append_interview_card(run_id, "interview.started")
        status = self.status(run_id)
        run = load_run(self.db_path, run_id)
        boardroom = self._boardroom_adapter().record_start(run, status["origin"])
        status["boardroom"] = boardroom
        return status

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
                        INSERT INTO minerva_runs (
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
        raise sqlite3.IntegrityError(f"Unable to reserve unique minerva run_id after retries: {last_error}")

    def turn(self, run_id: str, message: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        message = _redact_text(message)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"created", "interviewing"}, "record interview turn")
        self._append_jsonl(run_id, "interview.jsonl", {"at": _now(), "role": "user", "message": message})
        turn_index = len(self._read_interview(run_id))
        self._update_interview_state_from_turn(run_id, run["goal"], message)
        self._append_interview_card(run_id, "interview.updated")
        if run["phase"] == "created":
            self._set_phase(run_id, "interviewing")
        status = self.status(run_id)
        refreshed_run = load_run(self.db_path, run_id)
        status["boardroom"] = self._boardroom_adapter().record_turn(refreshed_run, message, turn_index)
        return status

    def seed(self, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"created", "interviewing", "seeded"}, "seed")
        seed_json = self._artifact_path(run_id, "seed.json")
        seed_md = self._artifact_path(run_id, "seed.md")
        if seed_json.exists() and seed_md.exists():
            seed = self._load_seed(run_id)
            result = self.status(run_id)
            result["created"] = False
            result["seed_version"] = int(run["seed_version"] or seed.get("version") or 1)
            result["boardroom"] = self._boardroom_adapter().record_seed(run, seed)
            return result

        interview = self._read_interview(run_id)
        interview_state = self._load_interview_state(run_id, run["goal"])
        unresolved = list(interview_state.get("unresolved") or [])
        if unresolved:
            raise ValueError(
                f"Cannot seed {run_id}: ambiguity {interview_state.get('ambiguity_score', 1.0)} is not seedable at threshold {AMBIGUITY_THRESHOLD}; unresolved interview dimensions remain: {', '.join(unresolved)}; continue the Discord interview first"
            )
        if float(interview_state.get("ambiguity_score", 1.0)) > AMBIGUITY_THRESHOLD:
            raise ValueError(
                f"Cannot seed {run_id}: ambiguity {interview_state['ambiguity_score']} is above threshold {AMBIGUITY_THRESHOLD}; continue the Discord interview first"
            )
        if not interview_state.get("alignment_checkpoints"):
            raise ValueError(f"Cannot seed {run_id}: no self-alignment checkpoint exists; record at least one user-alignment turn before seeding")
        acceptance = self._acceptance_from_interview(interview)
        minerva_process_gate = self._minerva_seed_process_gate(interview_state)
        workflow_design = self._workflow_design_from_interview(run_id, run, interview_state, acceptance)
        seed = {
            "run_id": run_id,
            "version": 1,
            "goal": run["goal"],
            "created_at": _now(),
            "ambiguity_score": interview_state["ambiguity_score"],
            "interview_gate": {"threshold": AMBIGUITY_THRESHOLD, "passed": True},
            "alignment_gate": {
                "policy": "self_reflect_align_choose_next_before_each_step",
                "checkpoint_count": len(interview_state.get("alignment_checkpoints") or []),
                "latest_checkpoint": (interview_state.get("alignment_checkpoints") or [None])[-1],
                "passed": bool(interview_state.get("alignment_checkpoints")),
            },
            "minerva_process_gate": minerva_process_gate,
            "workflow_design": workflow_design,
            "decisions": interview_state.get("decisions", {}),
            "acceptance_criteria": acceptance,
            "constraints": [
                "ZeusOS workspace artifacts only",
                "No Hermes source/config mutation",
                "No external service calls",
                "Seed v1 is immutable; evolve writes proposals instead of hidden mutation",
            ],
        }
        self._write_json(run_id, "workflow_design.json", workflow_design)
        self._write_json(run_id, "seed.json", seed)
        seed_md.write_text(self._seed_markdown(seed), encoding="utf-8")
        self._set_phase(run_id, "seeded", seed_version=1)
        refreshed_run = load_run(self.db_path, run_id)
        result = self.status(run_id)
        result["created"] = True
        result["seed_version"] = 1
        result["seed"] = seed
        result["boardroom"] = self._boardroom_adapter().record_seed(refreshed_run, seed)
        return result

    def run(self, run_id: str, executor: str = "") -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        self._require_phase(run_id, run["phase"], {"seeded", "running"}, "run")
        seed = self._load_seed(run_id)
        workflow_design = self._load_workflow_design(run_id, seed)
        gate = dict(dict(workflow_design.get("phase_gate") or {}).get("gate") or {})
        if gate.get("allowed") is not True:
            failed = ", ".join(str(item) for item in gate.get("failed_dimensions") or []) or "unknown"
            raise ValueError(f"Cannot run {run_id}: workflow design gate failed ({failed}); return to Minerva planning/critic before execution")
        executor_name = executor or str(seed.get("decisions", {}).get("executor") or "deterministic-placeholder")
        if executor_name in {"claude-code", "claude_code"}:
            self._write_claude_code_handoff(run_id, seed)
            mode = "claude_code_handoff"
            limitation = "Claude Code execution is deferred to an explicit worker; this command only writes the handoff contract"
        else:
            mode = "deterministic placeholder"
            limitation = "placeholder evidence is synthetic and only suitable for dry-run workflow validation"
        lines = [
            "# Minerva Execution Log",
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
            "# Minerva Evaluation",
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
            "# Minerva Evolution Proposal",
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
        result = {
            "run_id": run_id,
            "goal": run["goal"],
            "phase": run["phase"],
            "execution_mode": self._execution_mode(run_id),
            "evaluation_mode": "placeholder_substring_match",
            "seed_version": run["seed_version"],
            "interview_state": self._load_interview_state(run_id, run["goal"]),
            "minerva_process_gate": self._minerva_process_gate_for_run(run_id, run),
            "origin": self._origin_metadata(run_id, run),
            "warnings": self._status_warnings(run_id, run),
            "artifacts": artifacts,
            "latest_drift": drift_path.read_text(encoding="utf-8") if drift_path.exists() else "",
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
        }
        boardroom = self._boardroom_adapter().read_summary(run_id)
        if boardroom:
            result["boardroom"] = boardroom
        return result

    def export(self, run_id: str) -> dict[str, Any]:
        _validate_run_id(run_id)
        run = load_run(self.db_path, run_id)
        return {
            "run": run,
            "status": self.status(run_id),
            "interview": self._read_interview(run_id),
            "seed": self._load_seed(run_id) if self._artifact_path(run_id, "seed.json").exists() else None,
            "artifacts": self._artifact_texts(run_id),
            "boardroom": self._boardroom_adapter().read_snapshot(run_id),
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
            conn.execute("UPDATE minerva_runs SET origin_thread_id = ?, updated_at = ? WHERE run_id = ?", (thread_id, _now(), run_id))
            conn.commit()
        refreshed_run = load_run(self.db_path, run_id)
        refreshed_status = self.status(run_id)
        refreshed_status["boardroom"] = self._boardroom_adapter().record_start(refreshed_run, refreshed_status["origin"])
        return refreshed_status

    def _boardroom_adapter(self) -> MinervaBoardroomAdapter:
        return MinervaBoardroomAdapter.from_workspace(self.workspace_root)

    def _set_phase(self, run_id: str, phase: str, seed_version: int | None = None) -> None:
        if phase not in PHASES:
            raise ValueError(f"Unknown minerva phase: {phase}")
        updated_at = _now()
        with sqlite3.connect(self.db_path) as conn:
            if seed_version is None:
                conn.execute("UPDATE minerva_runs SET phase = ?, updated_at = ? WHERE run_id = ?", (phase, updated_at, run_id))
            else:
                conn.execute("UPDATE minerva_runs SET phase = ?, seed_version = ?, updated_at = ? WHERE run_id = ?", (phase, seed_version, updated_at, run_id))
            conn.commit()

    def _require_phase(self, run_id: str, phase: str, allowed: set[str], action: str) -> None:
        if phase not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(f"Invalid minerva transition for {run_id}: cannot {action} from phase {phase}; expected one of: {allowed_text}")

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
        name = thread_name or f"minerva {run_id}"
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
        return self.workspace_root / "data" / "minerva" / run_id

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
            raise FileNotFoundError(f"Seed does not exist for run {run_id}; run `minerva seed` first")
        return json.loads(seed_path.read_text(encoding="utf-8"))

    def _load_workflow_design(self, run_id: str, seed: dict[str, Any]) -> dict[str, Any]:
        design_path = self._artifact_path(run_id, "workflow_design.json")
        if design_path.exists():
            return json.loads(design_path.read_text(encoding="utf-8"))
        embedded = seed.get("workflow_design")
        if isinstance(embedded, dict):
            return embedded
        raise FileNotFoundError(f"Workflow design does not exist for run {run_id}; run `minerva seed` first")

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
            "alignment_checkpoints": [],
            "updated_at": _now(),
        }

    def _load_interview_state(self, run_id: str, goal: str) -> dict[str, Any]:
        path = self._artifact_path(run_id, "interview_state.json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return self._initial_interview_state(run_id, goal)

    def _write_interview_state(self, run_id: str, state: dict[str, Any]) -> None:
        self._write_json(run_id, "interview_state.json", state)

    def _next_unresolved_dimension(self, state: dict[str, Any]) -> str | None:
        resolved = set(state.get("resolved", []))
        for dimension in INTERVIEW_DIMENSIONS:
            if dimension not in resolved:
                return dimension
        return None

    def _proposal_for(self, dimension: str, option_id: str) -> dict[str, str]:
        for candidate_id, label, value in INTERVIEW_PROPOSALS[dimension]:
            if candidate_id == option_id:
                return {"option_id": candidate_id, "label": label, "value": value}
        raise ValueError(f"Unknown Minerva proposal option: {dimension}/{option_id}")

    def _recompute_interview_gate(self, state: dict[str, Any]) -> None:
        resolved = set(state.get("resolved", []))
        unresolved = [key for key in INTERVIEW_DIMENSIONS if key not in resolved]
        score = round(len(unresolved) / len(INTERVIEW_DIMENSIONS), 2)
        state.update({
            "ambiguity_score": score,
            "seed_ready": not unresolved and score <= AMBIGUITY_THRESHOLD,
            "resolved": [key for key in INTERVIEW_DIMENSIONS if key in resolved],
            "unresolved": unresolved,
            "updated_at": _now(),
        })

    def _apply_proposal_choice(self, run_id: str, goal: str, dimension: str, option_id: str, actor_id: str = "") -> dict[str, Any]:
        if dimension not in INTERVIEW_DIMENSIONS:
            raise ValueError(f"Unknown Minerva proposal dimension: {dimension}")
        if option_id not in PROPOSAL_OPTION_IDS:
            raise ValueError(f"Unknown Minerva proposal option: {option_id}")
        state = self._load_interview_state(run_id, goal)
        expected_dimension = self._next_unresolved_dimension(state)
        if expected_dimension != dimension:
            raise ValueError(f"Minerva proposal dimension mismatch: expected {expected_dimension or 'none'}, got {dimension}")
        proposal = self._proposal_for(dimension, option_id)
        decisions = dict(state.get("decisions") or {})
        decisions[dimension] = proposal["value"]
        resolved = set(state.get("resolved", []))
        resolved.add(dimension)
        state["decisions"] = decisions
        state["resolved"] = [key for key in INTERVIEW_DIMENSIONS if key in resolved]
        if state.get("pending_freeform_dimension") == dimension:
            state.pop("pending_freeform_dimension", None)
        self._recompute_interview_gate(state)
        self._append_alignment_checkpoint(
            state,
            goal=goal,
            user_instruction=f"{INTERVIEW_DIMENSION_LABELS[dimension]}: {proposal['value']}",
            source="proposal_button",
        )
        state.setdefault("decision_log", []).append({
            "at": _now(),
            "source": "proposal_button",
            "dimension": dimension,
            "option_id": option_id,
            "value": proposal["value"],
            "actor_id": actor_id or None,
            "resolved": state["resolved"],
            "ambiguity_score": state["ambiguity_score"],
        })
        self._write_interview_state(run_id, state)
        self._append_jsonl(run_id, "interview.jsonl", {
            "at": _now(),
            "role": "user",
            "message": f"{INTERVIEW_DIMENSION_LABELS[dimension]}: {proposal['value']}",
            "source": "proposal_button",
            "dimension": dimension,
            "option_id": option_id,
        })
        return state

    def _record_other_opinion_request(self, run_id: str, goal: str, dimension: str, actor_id: str = "") -> dict[str, Any]:
        if dimension not in INTERVIEW_DIMENSIONS:
            raise ValueError(f"Unknown Minerva proposal dimension: {dimension}")
        state = self._load_interview_state(run_id, goal)
        expected_dimension = self._next_unresolved_dimension(state)
        if expected_dimension != dimension:
            raise ValueError(f"Minerva proposal dimension mismatch: expected {expected_dimension or 'none'}, got {dimension}")
        state.setdefault("pending_freeform_dimension", dimension)
        self._append_alignment_checkpoint(
            state,
            goal=goal,
            user_instruction=f"Other opinion requested for {INTERVIEW_DIMENSION_LABELS[dimension]}",
            source="other_opinion_button",
        )
        state.setdefault("decision_log", []).append({
            "at": _now(),
            "source": "other_opinion_button",
            "dimension": dimension,
            "actor_id": actor_id or None,
            "instruction": f"Reply with `{INTERVIEW_DIMENSION_LABELS[dimension]}: ...` to resolve this dimension.",
            "resolved": state.get("resolved", []),
            "ambiguity_score": state.get("ambiguity_score", 1.0),
        })
        state["updated_at"] = _now()
        self._write_interview_state(run_id, state)
        return state

    def _record_button_alignment(self, run_id: str, goal: str, *, action: str, user_instruction: str) -> dict[str, Any]:
        state = self._load_interview_state(run_id, goal)
        self._append_alignment_checkpoint(
            state,
            goal=goal,
            user_instruction=user_instruction,
            source=f"{action}_button",
        )
        state.setdefault("decision_log", []).append({
            "at": _now(),
            "source": f"{action}_button",
            "message": user_instruction,
            "resolved": state.get("resolved", []),
            "ambiguity_score": state.get("ambiguity_score", 1.0),
        })
        self._write_interview_state(run_id, state)
        return state

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
        pending_dimension = str(state.get("pending_freeform_dimension") or "")
        if freeform and pending_dimension in INTERVIEW_DIMENSIONS and message.strip():
            expected_dimension = self._next_unresolved_dimension(state)
            if expected_dimension == pending_dimension:
                resolved.add(pending_dimension)
                decisions[pending_dimension] = message.strip()
                freeform = False
        if freeform and message.strip():
            decisions.setdefault("notes", []).append(message.strip())
        state["resolved"] = [key for key in INTERVIEW_DIMENSIONS if key in resolved]
        state["decisions"] = decisions
        if not freeform:
            state.pop("pending_freeform_dimension", None)
        self._recompute_interview_gate(state)
        state.setdefault("decision_log", []).append({"at": _now(), "message": message, "resolved": state["resolved"], "ambiguity_score": state["ambiguity_score"]})
        self._append_alignment_checkpoint(state, goal=goal, user_instruction=message, source="user_turn")
        self._write_interview_state(run_id, state)

    def _append_alignment_checkpoint(self, state: dict[str, Any], *, goal: str, user_instruction: str, source: str) -> None:
        unresolved = list(state.get("unresolved") or [])
        seed_ready = bool(state.get("seed_ready"))
        if seed_ready:
            direction = "seed_ready_preserve_alignment"
            chosen_next_step = "propose_seed"
            requires_operator_decision = False
        elif unresolved:
            direction = "continue_interview_until_seed_ready"
            chosen_next_step = "resolve_next_interview_dimension"
            requires_operator_decision = True
        else:
            direction = "verify_before_execution"
            chosen_next_step = "run_preflight_verification"
            requires_operator_decision = False
        checkpoints = list(state.get("alignment_checkpoints") or [])
        checkpoints.append({
            "at": _now(),
            "source": source,
            "user_instruction": _redact_text(user_instruction.strip()),
            "active_goal": _redact_text(goal.strip()),
            "alignment_question": "Does the next action still serve the user's latest instruction and the run goal?",
            "direction": direction,
            "chosen_next_step": chosen_next_step,
            "resolved": list(state.get("resolved") or []),
            "unresolved": unresolved,
            "ambiguity_score": state.get("ambiguity_score", 1.0),
            "requires_operator_decision": requires_operator_decision,
            "stop_before_live_boundary": True,
        })
        state["alignment_checkpoints"] = checkpoints

    def _append_interview_card(self, run_id: str, event: str) -> dict[str, Any]:
        run = load_run(self.db_path, run_id)
        state = self._load_interview_state(run_id, run["goal"])
        origin = self._origin_metadata(run_id, run)
        revision = self._next_card_revision(run_id)
        card_id = f"minerva-interview:{run_id}"
        target_thread_id = origin.get("thread_id") or (origin.get("thread") or {}).get("thread_id")
        next_dimension = self._next_unresolved_dimension(state)
        components = self._interview_components(run_id, revision, bool(state["seed_ready"]), next_dimension)
        card = {
            "action": "discord.interaction_message",
            "contract_version": 2,
            "event": event,
            "run_id": run_id,
            "card_id": card_id,
            "card_revision": revision,
            "idempotency_key": f"minerva:discord-card:{run_id}:{revision}",
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
                "allowed_actions": ["select_proposal", "other_opinion", "continue_interview", "propose_seed", "cancel"],
                "reject_stale_revision": True,
                "validate_run_id": True,
                "validate_channel_thread": True,
                "do_not_bypass_ambiguity_gate": True,
                "side_effect_class": "zeusos_workspace_write_only",
            },
            "card": {
                "kind": "interview",
                "title": "Minerva Interview",
                "goal": run["goal"],
                "goal_summary": self._display_text(run["goal"]),
                "ambiguity_score": state["ambiguity_score"],
                "threshold": AMBIGUITY_THRESHOLD,
                "seed_ready": state["seed_ready"],
                "unresolved": state["unresolved"],
                "decisions": self._display_decisions(state.get("decisions", {})),
                "alignment_checkpoint": (state.get("alignment_checkpoints") or [None])[-1],
                "minerva_process_gate": self._minerva_process_gate_for_run(run_id, run, state),
                "proposal_card": self._proposal_card(next_dimension),
                "buttons": [component["action"] for component in components],
                "components": components,
            },
        }
        self._append_jsonl(run_id, "discord_cards.jsonl", card)
        return card

    def _proposal_card(self, dimension: str | None) -> dict[str, Any] | None:
        if dimension is None:
            return None
        proposals = [
            {"option_id": option_id, "label": label, "value": value}
            for option_id, label, value in INTERVIEW_PROPOSALS[dimension]
        ]
        return {
            "dimension": dimension,
            "label": INTERVIEW_DIMENSION_LABELS[dimension],
            "prompt": f"Choose a concrete {dimension} proposal, or choose Other to provide a new opinion for this dimension.",
            "proposals": proposals,
            "other": {
                "action": "other_opinion",
                "label": "Other / new opinion",
                "expected_reply": f"{INTERVIEW_DIMENSION_LABELS[dimension]}: <your value>",
            },
        }

    def _interview_components(self, run_id: str, revision: int, seed_ready: bool, dimension: str | None) -> list[dict[str, Any]]:
        if dimension is not None:
            components = []
            for option_id, label, _value in INTERVIEW_PROPOSALS[dimension]:
                custom_id = f"minerva:v2:select_proposal:{run_id}:r{revision}:d{dimension}:o{option_id}"
                if len(custom_id) > 100:
                    raise ValueError(f"Discord custom_id too long for {run_id}: select_proposal")
                components.append({
                    "type": "button",
                    "action": "select_proposal",
                    "dimension": dimension,
                    "option_id": option_id,
                    "label": f"{option_id.upper()}. {label}",
                    "style": "primary",
                    "disabled": False,
                    "custom_id": custom_id,
                    "requires_seed_ready": False,
                    "requires_explicit_operator_approval": True,
                    "allowed_phase": ["created", "interviewing"],
                })
            custom_id = f"minerva:v2:other_opinion:{run_id}:r{revision}:d{dimension}:oother"
            if len(custom_id) > 100:
                raise ValueError(f"Discord custom_id too long for {run_id}: other_opinion")
            components.append({
                "type": "button",
                "action": "other_opinion",
                "dimension": dimension,
                "option_id": "other",
                "label": "Other / new opinion",
                "style": "secondary",
                "disabled": False,
                "custom_id": custom_id,
                "requires_seed_ready": False,
                "requires_explicit_operator_approval": True,
                "allowed_phase": ["created", "interviewing"],
            })
            return components

        specs = [
            ("continue_interview", "Continue Interview", "secondary", False, False, ["created", "interviewing"]),
            ("propose_seed", "Propose Seed", "primary", not seed_ready, True, ["created", "interviewing", "seeded"]),
            ("cancel", "Cancel", "danger", False, False, ["created", "interviewing"]),
        ]
        components = []
        for action, label, style, disabled, requires_seed_ready, allowed_phase in specs:
            custom_id = f"minerva:v2:{action}:{run_id}:r{revision}"
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

    def _parse_interaction_custom_id(self, custom_id: str) -> tuple[str, str, int, str, str]:
        match = re.fullmatch(r"minerva:v2:([a-z_]+):([A-Za-z0-9_.-]+):r([0-9]+)(?::d([a-z]+):o([a-z]+))?", custom_id or "")
        if not match:
            raise ValueError("Invalid Minerva Discord interaction custom_id")
        action, run_id, revision = match.group(1), match.group(2), int(match.group(3))
        dimension = match.group(4) or ""
        option_id = match.group(5) or ""
        _validate_run_id(run_id)
        return action, run_id, revision, dimension, option_id

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
        dimension = ""
        option_id = ""
        if custom_id:
            parsed_action, parsed_run_id, parsed_revision, parsed_dimension, parsed_option_id = self._parse_interaction_custom_id(custom_id)
            if parsed_run_id != run_id:
                raise ValueError("Discord interaction run_id mismatch")
            if action and action != parsed_action:
                raise ValueError("Discord interaction action/custom_id mismatch")
            action = parsed_action
            card_revision = parsed_revision
            dimension = parsed_dimension
            option_id = parsed_option_id
        if action not in {"select_proposal", "other_opinion", "continue_interview", "propose_seed", "cancel"}:
            raise ValueError(f"Unknown Minerva interaction action: {action}")
        if card_revision is None:
            raise ValueError("Discord interaction card_revision is required")
        run = load_run(self.db_path, run_id)
        allowed_by_action = {
            "select_proposal": {"created", "interviewing"},
            "other_opinion": {"created", "interviewing"},
            "continue_interview": {"created", "interviewing"},
            "propose_seed": {"created", "interviewing", "seeded"},
            "cancel": {"created", "interviewing"},
        }
        if run["phase"] not in allowed_by_action[action]:
            allowed_text = ", ".join(sorted(allowed_by_action[action]))
            raise ValueError(f"Invalid Minerva interaction {action} from phase {run['phase']}; expected one of: {allowed_text}")
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
            raise ValueError(f"Stale or unknown Minerva interaction card revision {card_revision}; latest is {latest_revision}")

        self._append_jsonl(run_id, "interaction_log.jsonl", {
            "at": _now(),
            "action": action,
            "card_revision": card_revision,
            "actor_id": actor_id or None,
            "origin_channel_id": origin_channel_id or None,
            "origin_thread_id": origin_thread_id or None,
            "side_effects": "zeusos_workspace_write_only",
            "dimension": dimension or None,
            "option_id": option_id or None,
        })
        if action == "select_proposal":
            if not dimension or not option_id:
                raise ValueError("Minerva proposal interaction requires dimension and option identity")
            self._apply_proposal_choice(run_id, run["goal"], dimension, option_id, actor_id)
            card = self._append_interview_card(run_id, "interview.proposal_selected")
            result = self.status(run_id)
            result["interaction"] = {
                "action": action,
                "handled": True,
                "dimension": dimension,
                "option_id": option_id,
                "card_revision": card["card_revision"],
                "next_unresolved": result["interview_state"].get("unresolved", []),
            }
            return result
        if action == "other_opinion":
            if not dimension:
                raise ValueError("Minerva other-opinion interaction requires dimension identity")
            self._record_other_opinion_request(run_id, run["goal"], dimension, actor_id)
            card = self._append_interview_card(run_id, "interview.other_requested")
            result = self.status(run_id)
            result["interaction"] = {
                "action": action,
                "handled": True,
                "dimension": dimension,
                "card_revision": card["card_revision"],
                "next_unresolved": result["interview_state"].get("unresolved", []),
                "expected_reply": f"{INTERVIEW_DIMENSION_LABELS[dimension]}: <your value>",
            }
            return result
        if action == "continue_interview":
            self._record_button_alignment(run_id, run["goal"], action=action, user_instruction="Continue interview requested")
            card = self._append_interview_card(run_id, "interview.continue_requested")
            result = self.status(run_id)
            result["interaction"] = {"action": action, "handled": True, "card_revision": card["card_revision"], "next_unresolved": result["interview_state"].get("unresolved", [])}
            return result
        if action == "propose_seed":
            self._record_button_alignment(run_id, run["goal"], action=action, user_instruction="Propose seed requested")
            result = self.seed(run_id)
            result["interaction"] = {"action": action, "handled": True, "gate_rechecked": True}
            return result
        self._record_button_alignment(run_id, run["goal"], action=action, user_instruction="Cancel requested")
        self._set_phase(run_id, "blocked")
        self._append_interview_card(run_id, "interview.cancelled")
        result = self.status(run_id)
        result["interaction"] = {"action": action, "handled": True, "terminal_phase": "blocked"}
        return result

    def _write_claude_code_handoff(self, run_id: str, seed: dict[str, Any]) -> None:
        command = "claude -p 'Execute this Minerva seed from stdin; implement only ZeusOS-owned changes, then run tests' --max-turns 10 --allowedTools 'Read,Edit,Write,Bash(PYTHONPATH=src pytest *),Bash(python -m compileall *)'"
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

    def _minerva_seed_process_gate(self, interview_state: dict[str, Any]) -> dict[str, object]:
        scores = {
            "alignment": 1.0 if interview_state.get("alignment_checkpoints") else 0.0,
            "consensus": 1.0 if not interview_state.get("unresolved") else 0.0,
            "clarity": max(0.0, min(1.0, 1.0 - float(interview_state.get("ambiguity_score", 1.0)))),
            "safety": 1.0,
            "evidence": 1.0 if interview_state.get("decisions") else 0.0,
        }
        return evaluate_phase_gate("critic_for_plan", scores)

    def _workflow_design_from_interview(
        self,
        run_id: str,
        run: dict[str, Any],
        interview_state: dict[str, Any],
        acceptance: list[str],
    ) -> dict[str, object]:
        decisions = dict(interview_state.get("decisions") or {})
        work_items = [
            {
                "id": f"acceptance-{index}",
                "source": "acceptance_criteria",
                "description": criterion,
                "status": "planned",
            }
            for index, criterion in enumerate(acceptance, start=1)
        ]
        scores = {
            "alignment": 1.0 if interview_state.get("alignment_checkpoints") else 0.0,
            "consensus": 1.0 if not interview_state.get("unresolved") else 0.0,
            "clarity": max(0.0, min(1.0, 1.0 - float(interview_state.get("ambiguity_score", 1.0)))),
            "safety": 1.0,
            "evidence": 1.0 if acceptance else 0.0,
        }
        return {
            "run_id": run_id,
            "goal": run["goal"],
            "phase_gate": phase_gate_card("workload_parsing_workflow_designing", scores),
            "work_items": work_items,
            "workflow": ["seed", "execute", "evaluate", "evolve"],
            "executor": decisions.get("executor") or "deterministic-placeholder",
            "parallelization": {
                "mode": "sequential-by-default",
                "parallel_allowed_when": "file-boundaries-are-provably-non-conflicting",
            },
            "safety": {
                "live_mutation": "forbidden-without-explicit-approval",
                "runtime_boundary": "ZeusOS-owned artifacts only",
                "rollback": "no-op for planning artifacts",
            },
            "self_heal": {
                "strategy": "review-align-gap-evolve",
                "on_gate_failure": "return-to-idea-direction-explore-or-recognize-missing-gap",
            },
        }

    def _minerva_process_gate_for_run(
        self,
        run_id: str,
        run: dict[str, Any],
        interview_state: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        state = interview_state or self._load_interview_state(run_id, run["goal"])
        phase_id = self._minerva_phase_id_for_run(run_id, run, state)
        scores = self._minerva_scores_for_phase(run_id, run, state, phase_id)
        return phase_gate_card(phase_id, scores)

    def _minerva_phase_id_for_run(self, run_id: str, run: dict[str, Any], interview_state: dict[str, Any]) -> str:
        phase = str(run.get("phase") or "")
        if phase in {"created", "interviewing"}:
            return "critic_for_plan" if interview_state.get("seed_ready") else "clarifying"
        if phase == "seeded":
            return "workload_parsing_workflow_designing"
        if phase == "running":
            return "execute"
        if phase == "evaluated":
            return "review_align_to_goal"
        if phase in {"blocked", "failed"}:
            return "recognize_missing_gap"
        if phase in {"evolved", "completed"}:
            return "evolving"
        return "user_question"

    def _minerva_scores_for_phase(
        self,
        run_id: str,
        run: dict[str, Any],
        interview_state: dict[str, Any],
        phase_id: str,
    ) -> dict[str, float]:
        resolved = set(interview_state.get("resolved") or [])
        unresolved = set(interview_state.get("unresolved") or [])
        resolved_ratio = len(resolved) / len(INTERVIEW_DIMENSIONS)
        scores = {
            "alignment": 1.0 if interview_state.get("alignment_checkpoints") else 0.0,
            "consensus": 1.0 if not unresolved else resolved_ratio,
            "clarity": max(0.0, min(1.0, 1.0 - float(interview_state.get("ambiguity_score", 1.0)))),
            "safety": 1.0,
            "evidence": 1.0 if interview_state.get("decisions") else resolved_ratio,
        }
        if phase_id == "execute":
            has_execution_log = self._artifact_path(run_id, "execution_log.md").exists()
            scores.update({
                "parallel": 1.0 if has_execution_log else 0.0,
                "safe": 1.0,
                "self_heal": 1.0 if self._artifact_path(run_id, "seed.json").exists() else 0.0,
            })
        return scores

    def _seed_markdown(self, seed: dict[str, Any]) -> str:
        lines = ["# Minerva Seed v1", "", f"Goal: {seed['goal']}", "", "## Acceptance Criteria"]
        lines.extend(f"- {criterion}" for criterion in seed["acceptance_criteria"])
        lines.extend(["", "## Constraints"])
        lines.extend(f"- {constraint}" for constraint in seed["constraints"])
        return "\n".join(lines) + "\n"

    def _drift_markdown(self, run_id: str, passed: bool, checks: list[dict[str, Any]]) -> str:
        failing = [check["criterion"] for check in checks if not check["passed"]]
        lines = ["# Minerva Drift", "", f"- Run ID: {run_id}", f"- Drift detected: {not passed}"]
        if failing:
            lines.extend(["", "## Missing Evidence"])
            lines.extend(f"- {criterion}" for criterion in failing)
        else:
            lines.extend(["", "No acceptance drift detected against recorded execution evidence."])
        return "\n".join(lines) + "\n"
