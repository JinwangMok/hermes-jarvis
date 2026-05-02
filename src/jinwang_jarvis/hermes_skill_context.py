from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .hermes_skill_search import search_skills


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else ""


def _snippet_text(snippet: dict[str, Any]) -> str:
    lines = [
        f"### {snippet['name']}",
        f"Path: {snippet['path']}",
        f"Score: {snippet['score']}",
    ]
    if snippet.get("purpose"):
        lines.append(f"Purpose: {snippet['purpose']}")
    if snippet.get("triggers"):
        lines.append(f"Triggers: {_format_list(snippet['triggers'])}")
    if snippet.get("tags"):
        lines.append(f"Tags: {_format_list(snippet['tags'])}")
    if snippet.get("related"):
        lines.append(f"Related: {_format_list(snippet['related'])}")
    if snippet.get("snippet"):
        lines.append(f"Snippet: {snippet['snippet']}")
    return "\n".join(lines)


def _payload_from_row(row: dict[str, Any], snippet_text: str | None = None) -> dict[str, Any]:
    return {
        "name": row["name"],
        "path": row["path"],
        "score": row["score"],
        "purpose": row.get("purpose", ""),
        "triggers": list(row.get("triggers") or []),
        "tags": list(row.get("tags") or []),
        "related": list(row.get("related") or []),
        "snippet": row.get("snippet", "") if snippet_text is None else snippet_text,
    }


def generate_skill_context(db_path: Path | str, query: str, budget_tokens: int = 2000, top_k: int = 5) -> dict[str, Any]:
    budget_tokens = max(1, int(budget_tokens))
    search_result = search_skills(db_path, query, top_k=top_k)
    if not search_result.get("ok"):
        return {**search_result, "budget_tokens": budget_tokens, "estimated_tokens": 0, "snippets": [], "context": ""}

    header = f"Hermes skill search context for query: {search_result['query']}"
    selected: list[dict[str, Any]] = []
    rendered: list[str] = []
    for row in search_result.get("rows", []):
        payload = _payload_from_row(row)
        candidate = _snippet_text(payload)
        candidate_context = "\n\n".join([header, *rendered, candidate])
        if estimate_tokens(candidate_context) <= budget_tokens:
            selected.append(payload)
            rendered.append(candidate)
            continue

        metadata_only = _payload_from_row(row, snippet_text="")
        metadata_text = _snippet_text(metadata_only)
        metadata_context = "\n\n".join([header, *rendered, metadata_text])
        if estimate_tokens(metadata_context) <= budget_tokens:
            selected.append(metadata_only)
            rendered.append(metadata_text)
            continue

        remaining_chars = max(0, budget_tokens * 4 - len("\n\n".join([header, *rendered, metadata_text])) - 8)
        if remaining_chars >= 40:
            truncated = str(row.get("snippet") or "")[:remaining_chars].rstrip()
            if truncated and len(truncated) < len(str(row.get("snippet") or "")):
                truncated += "…"
            truncated_payload = _payload_from_row(row, snippet_text=truncated)
            truncated_text = _snippet_text(truncated_payload)
            truncated_context = "\n\n".join([header, *rendered, truncated_text])
            if estimate_tokens(truncated_context) <= budget_tokens:
                selected.append(truncated_payload)
                rendered.append(truncated_text)

    context = "\n\n".join([header, *rendered]) if rendered else header
    while rendered and estimate_tokens(context) > budget_tokens:
        rendered.pop()
        selected.pop()
        context = "\n\n".join([header, *rendered]) if rendered else header
    if estimate_tokens(context) > budget_tokens:
        context = header[: max(0, budget_tokens * 4)]

    return {
        "ok": True,
        "database_path": search_result["database_path"],
        "query": search_result["query"],
        "budget_tokens": budget_tokens,
        "estimated_tokens": estimate_tokens(context),
        "top_k": top_k,
        "snippets": selected,
        "context": context,
    }
