from __future__ import annotations

import json
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WikiGovernance:
    """Runtime view of Jinwang's LLM Wiki governance layer.

    jinwang-jarvis treats the wiki as a dynamic knowledge substrate for Hermes:
    operational data stays in SQLite/artifacts, generated wiki pages are derived
    views, and only promoted/curated facts become durable entity/concept/query
    knowledge.
    """

    root: Path

    @property
    def schema_path(self) -> Path:
        return self.root / "SCHEMA.md"

    @property
    def document_responsibility_policy(self) -> Path:
        return self.root / "_meta/policies/document-responsibility.md"

    @property
    def generated_report_contract(self) -> Path:
        return self.root / "_meta/policies/generated-report-contract.md"

    @property
    def automation_pipeline_policy(self) -> Path:
        return self.root / "_meta/policies/wiki-automation-pipeline.md"

    @property
    def lint_script(self) -> Path:
        return self.root / "_meta/scripts/wiki_lint.py"

    @property
    def review_queue_dir(self) -> Path:
        return self.root / "_meta/review-queue"

    @property
    def ingestion_queue_path(self) -> Path:
        return self.root / "_meta/ingestion-queue.md"

    @property
    def run_metadata_dir(self) -> Path:
        return self.root / "_meta/runs"

    @property
    def available_policy_paths(self) -> tuple[Path, ...]:
        return tuple(
            path
            for path in (
                self.schema_path,
                self.document_responsibility_policy,
                self.generated_report_contract,
                self.automation_pipeline_policy,
            )
            if path.exists()
        )

    def ensure_operational_dirs(self) -> None:
        for path in (self.review_queue_dir, self.run_metadata_dir, self.ingestion_queue_path.parent):
            path.mkdir(parents=True, exist_ok=True)

    def policy_summary(self) -> dict[str, object]:
        return {
            "schema": str(self.schema_path),
            "document_responsibility_policy": str(self.document_responsibility_policy),
            "generated_report_contract": str(self.generated_report_contract),
            "automation_pipeline_policy": str(self.automation_pipeline_policy),
            "lint_script": str(self.lint_script),
            "policies_present": [str(path) for path in self.available_policy_paths],
        }


@dataclass(frozen=True)
class EvidenceRef:
    source_id: str
    source_kind: str
    source_url: str = ""
    source_hash: str = ""
    observed_at: str = ""
    confidence: float | None = None


def wiki_governance(wiki_root: Path) -> WikiGovernance:
    governance = WikiGovernance(wiki_root)
    governance.ensure_operational_dirs()
    return governance


def yaml_scalar(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if any(ch in text for ch in [":", "#", "[", "]", "{", "}", "\n"]):
        return json.dumps(text, ensure_ascii=False)
    return text


def yaml_list(values: Iterable[str]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


SECRET_ASSIGNMENT_RE = re.compile(r"(?i)\b(password|token|api_key|secret)\b\s*([=:])\s*([^\s,;`]+)")


def redact_obvious_secrets(text: str) -> str:
    return SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)


def stable_source_hash(payload: object) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_evidence_line(label: str, evidence: EvidenceRef) -> str:
    parts = [f"- {redact_obvious_secrets(label)}: `{redact_obvious_secrets(evidence.source_id)}`", f"kind={redact_obvious_secrets(evidence.source_kind)}"]
    if evidence.source_url:
        parts.append(f"url={redact_obvious_secrets(evidence.source_url)}")
    if evidence.source_hash:
        parts.append(f"hash={redact_obvious_secrets(evidence.source_hash)}")
    if evidence.observed_at:
        parts.append(f"observed_at={redact_obvious_secrets(evidence.observed_at)}")
    if evidence.confidence is not None:
        parts.append(f"confidence={evidence.confidence:.2f}")
    return " | ".join(parts)


def render_status_block(
    *,
    tldr: str,
    current_status: str,
    last_verified: str,
    evidence_coverage: str,
    open_questions: str,
) -> list[str]:
    return [
        "## Status",
        f"- TL;DR: {redact_obvious_secrets(tldr)}",
        f"- Current status: {redact_obvious_secrets(current_status)}",
        f"- Last verified: {redact_obvious_secrets(last_verified)}",
        f"- Evidence coverage: {redact_obvious_secrets(evidence_coverage)}",
        f"- Open questions: {redact_obvious_secrets(open_questions)}",
    ]


def render_frontmatter(
    *,
    title: str,
    created: str,
    updated: str,
    page_type: str,
    tags: list[str],
    sources: list[str] | None = None,
    subtype: str | None = None,
    owner: str = "jarvis",
    authority: str = "derived",
    generated: bool = True,
    generator: str = "jinwang-jarvis",
    refresh_policy: str = "overwrite",
    operational_source_of_truth: str | None = None,
    aliases: list[str] | None = None,
    summary: str | None = None,
) -> list[str]:
    lines = [
        "---",
        f"title: {yaml_scalar(title)}",
        f"created: {created}",
        f"updated: {updated}",
        f"type: {page_type}",
    ]
    if subtype:
        lines.append(f"subtype: {subtype}")
    lines.extend(
        [
            f"tags: {yaml_list(tags)}",
            f"sources: {yaml_list(sources or [])}",
            f"owner: {owner}",
            f"authority: {authority}",
            f"generated: {str(generated).lower()}",
            f"generator: {generator}",
            f"refresh_policy: {refresh_policy}",
        ]
    )
    if operational_source_of_truth:
        lines.append(f"operational_source_of_truth: {yaml_scalar(operational_source_of_truth)}")
    if aliases:
        lines.append(f"aliases: {yaml_list(aliases)}")
    if summary:
        lines.append(f"summary: {yaml_scalar(summary)}")
    lines.extend(["---", ""])
    return lines


def render_generated_report_frontmatter(
    *,
    title: str,
    date: str,
    subtype: str,
    tags: list[str],
    operational_source_of_truth: str,
    summary: str | None = None,
    refresh_policy: str = "overwrite",
    authority: str = "derived",
) -> list[str]:
    return render_frontmatter(
        title=title,
        created=date,
        updated=date,
        page_type="query",
        subtype=subtype,
        tags=tags,
        owner="jarvis",
        authority=authority,
        generated=True,
        generator="jinwang-jarvis",
        refresh_policy=refresh_policy,
        operational_source_of_truth=operational_source_of_truth,
        summary=summary,
    )


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    tmp_path.replace(path)


def run_wiki_lint_if_available(wiki_root: Path) -> dict[str, object] | None:
    lint_script = WikiGovernance(wiki_root).lint_script
    if not lint_script.exists():
        return None
    completed = subprocess.run([str(lint_script)], cwd=str(wiki_root), check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return {"ok": False, "returncode": completed.returncode, "stderr": completed.stderr.strip()}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": True, "raw_stdout": completed.stdout.strip()}
    payload["ok"] = True
    return payload


def wiki_operational_source(config: object) -> str:
    """Return the configured operational source behind Jarvis-generated wiki views."""
    database_path = getattr(config, "database_path", None)
    if database_path is not None:
        return str(database_path)
    workspace_root = getattr(config, "workspace_root", None)
    if workspace_root is not None:
        return str(Path(workspace_root) / "state" / "personal_intel.db")
    return "jinwang-jarvis configured SQLite database/artifacts"
