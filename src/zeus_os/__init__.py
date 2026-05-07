from .backfill import run_next_backfill_step, run_progressive_backfill
from .bootstrap import REQUIRED_DIRECTORIES, bootstrap_workspace
from .briefing import generate_briefing
from .calendar import collect_calendar_snapshots
from .classifier import classify_messages
from .config import PipelineConfig, load_pipeline_config
from .digest import generate_digest
from .feedback import record_proposal_feedback
from .knowledge import synthesize_knowledge
from .mail import collect_mail_snapshots
from .proposals import generate_proposals
from .review import generate_weekly_review
from .runtime import build_systemd_unit_texts, install_systemd_user_units, run_pipeline_cycle

__all__ = [
    "PipelineConfig",
    "REQUIRED_DIRECTORIES",
    "bootstrap_workspace",
    "build_systemd_unit_texts",
    "classify_messages",
    "collect_calendar_snapshots",
    "collect_mail_snapshots",
    "generate_briefing",
    "generate_digest",
    "generate_proposals",
    "generate_weekly_review",
    "install_systemd_user_units",
    "load_pipeline_config",
    "record_proposal_feedback",
    "run_next_backfill_step",
    "run_pipeline_cycle",
    "run_progressive_backfill",
    "synthesize_knowledge",
]

# Canonical top-level aliases for control-plane modules that remain grouped
# under zeus_os.zeus_os internally during the package cutover.
import importlib as _importlib
import sys as _sys

_CONTROL_PLANE_MODULES = [
    "a2a", "adapters", "artifacts", "boardroom", "doctor", "events", "export", "ids",
    "painter", "queue", "safety", "schema", "store", "worker",
]

for _module_name in _CONTROL_PLANE_MODULES:
    _module = _importlib.import_module(f"{__name__}.zeus_os.{_module_name}")
    _sys.modules.setdefault(f"{__name__}.{_module_name}", _module)
    globals().setdefault(_module_name, _module)

__canonical_name__ = "zeus_os"
