"""Deterministic ID generation for Zeus OS entities."""

from __future__ import annotations

import secrets
import string
import time
import uuid
from typing import Literal


_KIND_PREFIXES: dict[str, str] = {
    "agent": "ag",
    "worker": "wk",
    "context": "ctx",
    "session": "ses",
    "message": "msg",
    "task": "tsk",
    "agenda": "agd",
    "decision": "dec",
    "approval": "apr",
    "event": "evt",
    "work_order": "wo",
    "queue": "q",
    "artifact": "art",
    "dashboard": "dash",
}


def generate_id(kind: str) -> str:
    """Generate a short, readable, collision-resistant identifier."""
    prefix = _KIND_PREFIXES.get(kind, kind[:3])
    timestamp = int(time.time())
    random_part = secrets.token_hex(4)
    return f"{prefix}_{timestamp:x}_{random_part}"


def generate_uuid() -> str:
    """Generate a standard UUID4 string."""
    return str(uuid.uuid4())


def generate_idempotency_key(label: str = "") -> str:
    """Generate an idempotency key from label + timestamp + randomness."""
    safe_label = "".join(c for c in label if c.isalnum() or c in "-_").lower()[:32]
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(3)
    return f"{safe_label}:{ts:x}:{rand}" if safe_label else f"{ts:x}:{rand}"
