from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class UnknownRootError(ValueError):
    """Raised when a logical ZeusOS root name is not supported."""


class MissingRootError(FileNotFoundError):
    """Raised when a supported root is expected but absent."""


@dataclass(frozen=True)
class RootPolicy:
    name: str
    path: Path
    category: str
    source_of_truth: str
    inventory_scannable: bool
    implicit_create_allowed: bool = False


_ROOT_SPECS: dict[str, tuple[str, str, str, bool]] = {
    "data": ("data", "legacy_runtime", "runtime_truth", False),
    "state": ("state", "legacy_runtime", "runtime_truth", False),
    "skills": ("skills", "legacy_runtime", "compatibility_alias", True),
    "scripts": ("scripts", "legacy_runtime", "compatibility_alias", True),
    "agents": ("agents", "declarative", "declarative_truth", True),
    "agent_shim": ("agent-shim", "declarative", "declarative_truth", True),
    "apps": ("apps", "declarative", "declarative_truth", True),
    "channels": ("channels", "declarative", "declarative_truth", True),
    "vmem": ("vmem", "local_private", "local_only", False),
    "journals": ("journals", "local_private", "local_only", True),
    "wiki": ("wiki", "local_private", "local_only", False),
    "assets": ("assets", "generated_asset", "local_only", True),
    "credentials": ("credentials", "local_private", "local_only", False),
    "workspace": ("workspace", "local_private", "local_only", True),
}


class ZeusPaths:
    """Read-only resolver for ZeusOS legacy and declarative roots."""

    def __init__(self, repo_root: Path | str) -> None:
        self.repo_root = Path(repo_root).expanduser().resolve()

    def resolve_root(self, name: str) -> Path:
        policy = self.root_policy(name)
        if not policy.path.exists():
            raise MissingRootError(f"ZeusOS root does not exist for {name!r}: {policy.path}")
        return policy.path

    def root_policy(self, name: str) -> RootPolicy:
        try:
            directory, category, source_of_truth, inventory_scannable = _ROOT_SPECS[name]
        except KeyError as exc:
            raise UnknownRootError(f"unsupported ZeusOS root: {name}") from exc
        return RootPolicy(
            name=name,
            path=self.repo_root / directory,
            category=category,
            source_of_truth=source_of_truth,
            inventory_scannable=inventory_scannable,
            implicit_create_allowed=False,
        )
