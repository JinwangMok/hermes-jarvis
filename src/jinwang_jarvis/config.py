from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml


@dataclass(frozen=True)
class WatchSettings:
    enabled: bool
    snapshot_dir: Path
    source_config_dir: Path
    default_poll_minutes: int
    adjudicator_model: str
    fallback_model: str | None
    importance_alert_threshold: float
    momentum_alert_threshold: float
    digest_threshold: float
    recency_hours: int
    story_similarity: float
    compare_window_hours: int
    target_companies: tuple[str, ...]
    subreddits: tuple[str, ...]
    enable_sources: dict[str, bool]


@dataclass(frozen=True)
class PipelineConfig:
    config_path: Path
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
    self_addresses: tuple[str, ...]
    work_accounts: tuple[str, ...]
    watch: WatchSettings


def _resolve_under_workspace(workspace_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace_root / path


def _resolve_from_config_dir(config_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (config_path.parent / path).resolve()


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
    config_path = Path(config_path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    workspace_root = _resolve_from_config_dir(config_path, str(raw["workspace_root"]))
    state = raw["state"]
    mail = raw["mail"]
    calendar = raw["calendar"]
    classification = raw.get("classification", {})
    hermes = raw["hermes"]
    reproducibility = raw["reproducibility"]
    watch = raw.get("watch", {})
    default_time_min, default_time_max = _default_calendar_window()

    watch_settings = WatchSettings(
        enabled=bool(watch.get("enabled", False)),
        snapshot_dir=_resolve_under_workspace(workspace_root, str(watch.get("snapshot_dir", "data/watch"))),
        source_config_dir=_resolve_under_workspace(workspace_root, str(watch.get("source_config_dir", "config/watch-sources"))),
        default_poll_minutes=int(watch.get("default_poll_minutes", 60)),
        adjudicator_model=str(watch.get("adjudicator_model", "gpt-5.4")),
        fallback_model=(str(watch["fallback_model"]) if watch.get("fallback_model") else None),
        importance_alert_threshold=float(watch.get("importance_alert_threshold", 0.82)),
        momentum_alert_threshold=float(watch.get("momentum_alert_threshold", 0.18)),
        digest_threshold=float(watch.get("digest_threshold", 0.60)),
        recency_hours=int(watch.get("recency_hours", 24)),
        story_similarity=float(watch.get("story_similarity", 0.84)),
        compare_window_hours=int(watch.get("compare_window_hours", 1)),
        target_companies=tuple(str(item) for item in watch.get("target_companies", [])),
        subreddits=tuple(str(item) for item in watch.get("subreddits", [])),
        enable_sources=dict(watch.get("enable_sources", {})),
    )

    return PipelineConfig(
        config_path=config_path,
        project_name=reproducibility["project_name"],
        workspace_root=workspace_root,
        wiki_root=_resolve_from_config_dir(config_path, str(raw["wiki_root"])),
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
        self_addresses=tuple(email.strip().lower() for email in classification.get("self_addresses", []) if str(email).strip()),
        work_accounts=tuple(str(account).strip() for account in classification.get("work_accounts", []) if str(account).strip()),
        watch=watch_settings,
    )
