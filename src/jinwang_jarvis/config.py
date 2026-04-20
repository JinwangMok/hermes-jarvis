from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PipelineConfig:
    project_name: str
    workspace_root: Path
    wiki_root: Path
    accounts: tuple[str, ...]
    database_path: Path
    checkpoints_path: Path
    sender_map_path: Path | None
    mail_snapshot_dir: Path
    mail_page_size: int
    sent_folder_overrides: dict[str, str]
    calendar_snapshot_dir: Path
    calendar_id: str
    calendar_max_results: int
    calendar_time_min: str
    calendar_time_max: str
    hermes_integration_mode: str
    deliver_channel: str


def _resolve_under_workspace(workspace_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace_root / path


def _stringify_time_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _default_calendar_window() -> tuple[str, str]:
    start = datetime.now().astimezone().replace(microsecond=0)
    end = start + timedelta(days=30)
    return start.isoformat(), end.isoformat()


def load_pipeline_config(config_path: Path) -> PipelineConfig:
    config_path = Path(config_path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    workspace_root = Path(raw["workspace_root"])
    state = raw["state"]
    mail = raw["mail"]
    calendar = raw["calendar"]
    classification = raw.get("classification", {})
    hermes = raw["hermes"]
    reproducibility = raw["reproducibility"]
    default_time_min, default_time_max = _default_calendar_window()

    return PipelineConfig(
        project_name=reproducibility["project_name"],
        workspace_root=workspace_root,
        wiki_root=Path(raw["wiki_root"]),
        accounts=tuple(raw.get("accounts", [])),
        database_path=_resolve_under_workspace(workspace_root, state["database"]),
        checkpoints_path=_resolve_under_workspace(workspace_root, state["checkpoints"]),
        sender_map_path=(_resolve_under_workspace(workspace_root, classification["sender_map_path"]) if classification.get("sender_map_path") else None),
        mail_snapshot_dir=_resolve_under_workspace(workspace_root, mail["snapshot_dir"]),
        mail_page_size=int(mail.get("page_size", 100)),
        sent_folder_overrides=dict(mail.get("sent_folder_overrides", {})),
        calendar_snapshot_dir=_resolve_under_workspace(workspace_root, calendar["snapshot_dir"]),
        calendar_id=calendar.get("calendar_id", "primary"),
        calendar_max_results=int(calendar.get("max_results", 50)),
        calendar_time_min=_stringify_time_value(calendar.get("time_min", default_time_min)),
        calendar_time_max=_stringify_time_value(calendar.get("time_max", default_time_max)),
        hermes_integration_mode=hermes["integration_mode"],
        deliver_channel=hermes["deliver_channel"],
    )
