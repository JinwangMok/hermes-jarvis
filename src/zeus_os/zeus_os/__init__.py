"""Zeus OS — deterministic, stdlib-only Agent OS control plane."""

from __future__ import annotations

__version__ = "0.1.0"

ZEUS_STATE_DIR = "state"
ZEUS_DB_NAME = "zeus_os.db"
ZEUS_ARTIFACT_ROOT = "data/zeus/tasks"


def get_default_db_path(workspace_root: str = ".") -> str:
    from pathlib import Path
    return str(Path(workspace_root) / ZEUS_STATE_DIR / ZEUS_DB_NAME)


def get_default_artifact_root(workspace_root: str = ".") -> str:
    from pathlib import Path
    return str(Path(workspace_root) / ZEUS_ARTIFACT_ROOT)
