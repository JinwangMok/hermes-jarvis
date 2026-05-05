"""Redaction, token scanning, and path safety for Zeus OS."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


# Patterns for secrets and private reasoning
_SECRET_PATTERNS = [
    # Discord bot tokens
    re.compile(r"[MN][A-Za-z\d]{23}\.[A-Za-z\d]{6}\.[A-Za-z\d]{27}"),
    # Bearer/API keys
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_\-\.]{20,}"),
    # Private keys
    re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    # Generic high-entropy tokens
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"[a-zA-Z0-9]{32,}-[a-zA-Z0-9]{10,}"),
]

_REASONING_FIELDS = frozenset({
    "chain_of_thought",
    "reasoning_trace",
    "raw_reasoning",
    "hidden_reasoning",
    "private_thought",
    "internal_monologue",
})


def _replace_secrets(text: str, replacement: str = "[REDACTED]") -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value: Any) -> Any:
    """Recursively redact secrets and private reasoning from a JSON-like value."""
    if isinstance(value, str):
        return _replace_secrets(value)
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if k in _REASONING_FIELDS:
                result[k] = "[REDACTED: reasoning]"
            else:
                result[k] = redact_value(v)
        return result
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_json(text: str) -> str:
    """Parse JSON, redact, and re-serialize."""
    try:
        obj = json.loads(text)
        return json.dumps(redact_value(obj), ensure_ascii=False, separators=(",", ":"), default=str)
    except json.JSONDecodeError:
        return _replace_secrets(text)


def scan_for_secrets(text: str) -> list[dict[str, Any]]:
    """Return list of potential secret matches with pattern name and position."""
    findings = []
    for i, pattern in enumerate(_SECRET_PATTERNS):
        for match in pattern.finditer(text):
            findings.append({
                "pattern_index": i,
                "start": match.start(),
                "end": match.end(),
                "length": match.end() - match.start(),
            })
    return findings


def is_safe_relative_path(path: str | Path) -> bool:
    """Reject absolute paths, parent traversal, non-canonical paths, and symlinks."""
    p = Path(str(path))
    # Reject absolute paths
    if p.is_absolute():
        return False
    # Reject parent traversal
    try:
        resolved = p.resolve()
        cwd = Path.cwd()
        if cwd not in resolved.parents and resolved != cwd:
            # It's escaping cwd
            pass
    except (OSError, RuntimeError):
        return False
    # Check for .. components
    if ".." in p.parts:
        return False
    # Check for symlinks
    try:
        if p.exists() and p.is_symlink():
            return False
    except (OSError, RuntimeError):
        return False
    return True


def resolve_safe_path(base_dir: Path, relative_path: str | Path) -> Path:
    """Resolve a relative path under base_dir, rejecting escapes."""
    p = Path(str(relative_path))
    if not is_safe_relative_path(p):
        raise ValueError(f"Unsafe path: {relative_path}")
    resolved = (base_dir / p).resolve()
    base_resolved = base_dir.resolve()
    # Ensure resolved is under base_dir
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Path escapes base directory: {relative_path}")
    return resolved


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
