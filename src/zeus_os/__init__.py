"""Canonical ZeusOS Python package facade.

Stage-1 migration keeps the existing implementation under ``jinwang_jarvis``
while exposing the new canonical import namespace.  Do not add new user-facing
surfaces to the legacy package; prefer ``zeus_os`` for new code.
"""

from __future__ import annotations

import importlib
import sys

from jinwang_jarvis import *  # noqa: F401,F403 - compatibility facade

_LEGACY_MODULES = [
    "backfill",
    "bootstrap",
    "briefing",
    "calendar",
    "classifier",
    "config",
    "digest",
    "feedback",
    "hermes_continuity",
    "hermes_skill_context",
    "hermes_skill_lifecycle",
    "hermes_skill_search",
    "houroboros",
    "intelligence",
    "knowledge",
    "mail",
    "news_center",
    "personal_radar",
    "proposals",
    "review",
    "runtime",
    "styled_voice_samples",
    "unified_daily_report",
    "watch",
    "wiki_contract",
    "wiki_search",
    "wiki_semantic_lint",
]

for _module_name in _LEGACY_MODULES:
    _module = importlib.import_module(f"jinwang_jarvis.{_module_name}")
    sys.modules.setdefault(f"{__name__}.{_module_name}", _module)
    globals().setdefault(_module_name, _module)

_CONTROL_PLANE_MODULES = [
    "a2a",
    "adapters",
    "artifacts",
    "boardroom",
    "doctor",
    "events",
    "export",
    "ids",
    "painter",
    "queue",
    "safety",
    "schema",
    "store",
    "worker",
]

for _module_name in _CONTROL_PLANE_MODULES:
    _module = importlib.import_module(f"jinwang_jarvis.zeus_os.{_module_name}")
    sys.modules.setdefault(f"{__name__}.{_module_name}", _module)
    globals().setdefault(_module_name, _module)

__canonical_name__ = "zeus_os"
