"""Painter workflow: deterministic fake image generation for MVP."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import artifacts, store


def create_painter_brief(
    artifact_root: Path,
    task_id: str,
    *,
    purpose: str = "",
    audience: str = "",
    desired_belief: str = "",
    medium: str = "digital illustration",
    aspect_ratio: str = "16:9",
    claims: list[str] | None = None,
    constraints: list[str] | None = None,
    style: str = "",
    cost_budget: dict[str, Any] | None = None,
    created_by: str = "painter",
) -> dict[str, Any]:
    brief_data = {
        "purpose": purpose,
        "audience": audience,
        "desired_belief": desired_belief,
        "medium": medium,
        "aspect_ratio": aspect_ratio,
        "claims": claims or [],
        "constraints": constraints or [],
        "style": style,
        "cost_budget": cost_budget or {},
    }
    record = artifacts.write_artifact(
        artifact_root=artifact_root,
        task_id=task_id,
        name="brief.md",
        kind="painter_brief",
        data=json.dumps(brief_data, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="text/markdown",
        created_by=created_by,
    )
    return record


def create_painter_prompt(
    artifact_root: Path,
    task_id: str,
    prompt_text: str,
    *,
    style_notes: str = "",
    created_by: str = "painter",
) -> dict[str, Any]:
    data = f"# Prompt\n\n{prompt_text}\n\n# Style\n\n{style_notes}\n".encode("utf-8")
    return artifacts.write_artifact(
        artifact_root=artifact_root,
        task_id=task_id,
        name="prompt.md",
        kind="painter_prompt",
        data=data,
        media_type="text/markdown",
        created_by=created_by,
    )


def generate_fake_image(
    artifact_root: Path,
    task_id: str,
    *,
    prompt: str = "",
    style: str = "",
    work_order_id: str | None = None,
    created_by: str = "painter",
) -> dict[str, Any]:
    fake_image_data = json.dumps({
        "_type": "fake_image",
        "prompt": prompt,
        "style": style,
        "dimensions": {"width": 1024, "height": 1024},
        "format": "png",
        "note": "This is a deterministic fake image placeholder. Live generation is gated.",
    }, ensure_ascii=False, indent=2).encode("utf-8")

    return artifacts.write_artifact(
        artifact_root=artifact_root,
        task_id=task_id,
        name="image.json",
        kind="fake_image",
        data=fake_image_data,
        media_type="application/json",
        work_order_id=work_order_id,
        created_by=created_by,
    )


def run_painter_workflow(
    conn: sqlite3.Connection,
    artifact_root: Path,
    task_id: str,
    *,
    purpose: str = "",
    prompt: str = "",
    style: str = "",
    work_order_id: str | None = None,
) -> list[dict[str, Any]]:
    records = []
    brief = create_painter_brief(artifact_root, task_id, purpose=purpose, style=style)
    records.append(brief)
    prompt_record = create_painter_prompt(artifact_root, task_id, prompt, style_notes=style)
    records.append(prompt_record)
    fake_image = generate_fake_image(artifact_root, task_id, prompt=prompt, style=style, work_order_id=work_order_id)
    records.append(fake_image)

    for record in records:
        artifacts.register_artifact(conn, record)

    return records
