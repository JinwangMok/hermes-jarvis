"""SQLite store: connection, transactions, and helper queries."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from . import schema


DEFAULT_PRAGMAS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
]


@dataclass(frozen=True)
class StoreConfig:
    db_path: str
    artifact_root: str
    workspace_root: str = "."

    @classmethod
    def from_workspace(cls, workspace_root: str = ".") -> "StoreConfig":
        from . import get_default_db_path, get_default_artifact_root
        return cls(
            db_path=get_default_db_path(workspace_root),
            artifact_root=get_default_artifact_root(workspace_root),
            workspace_root=workspace_root,
        )


def init_store(config: StoreConfig) -> sqlite3.Connection:
    """Initialize SQLite connection with WAL and pragmas."""
    Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.db_path, isolation_level=None, timeout=10.0)
    conn.row_factory = sqlite3.Row
    for pragma in DEFAULT_PRAGMAS:
        conn.execute(pragma)
    schema.apply_migrations(conn)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """BEGIN IMMEDIATE transaction context manager."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def json_loads(text: str | None) -> Any:
    if text is None:
        return None
    return json.loads(text)


def allocate_sequence(conn: sqlite3.Connection, task_id: str) -> int:
    """Atomically allocate the next event sequence for a task."""
    cur = conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) + 1 FROM task_events WHERE task_id = ?",
        (task_id,),
    )
    return cur.fetchone()[0]


def upsert_runtime_metadata(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO runtime_metadata (key, value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_json=excluded.value_json,
            updated_at=excluded.updated_at
        """,
        (key, json_dumps(value), now_utc()),
    )
