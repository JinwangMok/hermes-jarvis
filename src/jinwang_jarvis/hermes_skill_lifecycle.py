from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DEFAULT_HERMES_HOME = Path.home() / ".hermes"
DEFAULT_STALE_AFTER_DAYS = 30
DEFAULT_ARCHIVE_AFTER_DAYS = 90
DEFAULT_NEGATIVE_CLAIM_TTL_DAYS = 14
DEFAULT_TELEMETRY_PATH = Path("state/hermes-skill-usage.json")
TELEMETRY_EVENTS = {"viewed", "used", "successful_apply", "patched"}

_NEGATIVE_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:does not|doesn't|do not|don't|cannot|can't|never)\s+work\b", re.IGNORECASE),
    re.compile(r"\b(?:unavailable|not available|not installed|missing|blocked|unsupported)\b", re.IGNORECASE),
    re.compile(r"\b(?:fails?|broken)\b", re.IGNORECASE),
    re.compile(r"\b(?:안\s*됨|작동하지\s*않|불가능|없음|미설치|막힘)\b", re.IGNORECASE),
)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _external_dirs_from_config(config_path: Path) -> list[Path]:
    raw = _load_yaml(config_path)
    skills = raw.get("skills") or {}
    dirs = skills.get("external_dirs") or []
    if isinstance(dirs, str):
        dirs = [dirs]
    if not isinstance(dirs, list):
        return []
    return [Path(str(item)).expanduser() for item in dirs if item]


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_usage(skill_dir: Path, telemetry_index: dict[str, Any] | None = None) -> dict[str, Any]:
    usage_path = skill_dir / ".usage.json"
    sidecar: dict[str, Any] = {}
    if usage_path.exists():
        try:
            raw = json.loads(usage_path.read_text(encoding="utf-8"))
            sidecar = raw if isinstance(raw, dict) else {"_invalid": True}
        except Exception:
            sidecar = {"_invalid": True}
    telemetry = _telemetry_for_skill(skill_dir, telemetry_index or {})
    if telemetry:
        merged = {**sidecar, **telemetry, "_source": "jarvis_telemetry"}
        if sidecar and not sidecar.get("_invalid"):
            merged["_source"] = "sidecar+jarvis_telemetry"
        return merged
    if sidecar:
        sidecar.setdefault("_source", "sidecar")
    return sidecar


def _load_telemetry(path: Path | str | None) -> dict[str, Any]:
    if path is None:
        return {}
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_telemetry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _telemetry_key(skill_dir: Path) -> str:
    return str(skill_dir.expanduser().resolve())


def _telemetry_for_skill(skill_dir: Path, telemetry_index: dict[str, Any]) -> dict[str, Any]:
    skills = telemetry_index.get("skills") or {}
    if not isinstance(skills, dict):
        return {}
    entry = skills.get(_telemetry_key(skill_dir)) or skills.get(str(skill_dir))
    return entry if isinstance(entry, dict) else {}


def _skill_roots(hermes_home: Path, hermes_config_path: Path, include_external_dirs: bool) -> list[dict[str, str]]:
    roots: list[dict[str, str]] = [{"kind": "builtin", "path": str(hermes_home / "skills")}]
    if include_external_dirs:
        roots.extend({"kind": "external", "path": str(path)} for path in _external_dirs_from_config(hermes_config_path))
    return roots


def _find_skill_dir(*, skill: str | None, skill_path: Path | str | None, roots: list[dict[str, str]]) -> tuple[Path, str, str]:
    if skill_path:
        path = Path(skill_path).expanduser()
        skill_md = path / "SKILL.md" if path.is_dir() else path
        skill_dir = skill_md.parent
        if not (skill_dir / "SKILL.md").exists():
            raise FileNotFoundError(f"SKILL.md not found under {skill_dir}")
        return skill_dir, _skill_name(skill_dir, skill_dir / "SKILL.md"), "explicit"
    if not skill:
        raise ValueError("skill or skill_path is required")
    matches: list[tuple[Path, str, str]] = []
    for root in roots:
        for candidate in _iter_skill_dirs(Path(root["path"]).expanduser()):
            name = _skill_name(candidate, candidate / "SKILL.md")
            if skill in {name, candidate.name, str(candidate)}:
                matches.append((candidate, name, root["kind"]))
    if not matches:
        raise FileNotFoundError(f"skill not found: {skill}")
    if len(matches) > 1:
        raise ValueError(f"ambiguous skill name: {skill}")
    return matches[0]


def record_skill_telemetry(
    *,
    skill: str | None = None,
    event: str,
    hermes_home: Path | str = DEFAULT_HERMES_HOME,
    hermes_config_path: Path | str | None = None,
    telemetry_path: Path | str = DEFAULT_TELEMETRY_PATH,
    skill_path: Path | str | None = None,
    include_external_dirs: bool = True,
    pinned: bool | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if event not in TELEMETRY_EVENTS:
        raise ValueError(f"unsupported telemetry event: {event}")
    hermes_home = Path(hermes_home).expanduser()
    hermes_config_path = Path(hermes_config_path).expanduser() if hermes_config_path else hermes_home / "config.yaml"
    telemetry_path = Path(telemetry_path).expanduser()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    roots = _skill_roots(hermes_home, hermes_config_path, include_external_dirs)
    skill_dir, name, source = _find_skill_dir(skill=skill, skill_path=skill_path, roots=roots)
    key = _telemetry_key(skill_dir)
    data = _load_telemetry(telemetry_path) or {}
    data.setdefault("version", 1)
    data.setdefault("skills", {})
    skills = data["skills"]
    if not isinstance(skills, dict):
        skills = {}
        data["skills"] = skills
    usage = skills.get(key) if isinstance(skills.get(key), dict) else {}
    usage.setdefault("created_at", now.isoformat())
    usage.update({"name": name, "path": str(skill_dir), "source": source})
    timestamp = now.isoformat()
    if event == "viewed":
        usage["last_viewed_at"] = timestamp
    elif event in {"used", "successful_apply"}:
        usage["last_used_at"] = timestamp
        usage["use_count"] = int(usage.get("use_count") or 0) + 1
        if event == "successful_apply":
            usage["last_successful_apply_at"] = timestamp
    elif event == "patched":
        usage["last_patched_at"] = timestamp
        usage["patch_count"] = int(usage.get("patch_count") or 0) + 1
    if pinned is not None:
        usage["pinned"] = bool(pinned)
    events = usage.get("events") if isinstance(usage.get("events"), list) else []
    events.append({"event": event, "at": timestamp})
    usage["events"] = events[-50:]
    skills[key] = usage
    data["updated_at"] = timestamp
    _write_telemetry(telemetry_path, data)
    return {"ok": True, "telemetry_path": str(telemetry_path), "skill_key": key, "usage": usage}


def _skill_name(skill_dir: Path, skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8", errors="replace")[:4096]
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(text[3:end]) or {}
                if isinstance(fm, dict) and fm.get("name"):
                    return str(fm["name"])
            except Exception:
                pass
    return skill_dir.name


def _negative_claims(skill_md: Path, *, now: datetime, last_signal_at: datetime | None, ttl_days: int) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    matches: list[str] = []
    for pattern in _NEGATIVE_CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            snippet = text[max(0, match.start() - 80): min(len(text), match.end() + 80)]
            cleaned = " ".join(snippet.split())
            if cleaned not in matches:
                matches.append(cleaned)
    age_days = (now - last_signal_at).days if last_signal_at else None
    return {
        "count": len(matches),
        "examples": matches[:3],
        "revalidate": bool(matches) and (age_days is None or age_days >= ttl_days),
        "basis_age_days": age_days,
        "ttl_days": ttl_days,
    }


def _iter_skill_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path.parent for path in root.rglob("SKILL.md") if path.is_file())


def _state_for(*, skill_dir: Path, usage: dict[str, Any], age_days: int | None, pinned: bool, stale_after_days: int, archive_after_days: int) -> str:
    explicit = usage.get("state")
    if explicit in {"active", "stale", "archived"}:
        return str(explicit)
    if ".archive" in skill_dir.parts or usage.get("archived_at"):
        return "archived"
    if pinned:
        return "active"
    if age_days is not None and age_days >= archive_after_days:
        return "stale"
    if age_days is not None and age_days >= stale_after_days:
        return "stale"
    return "active"


def audit_hermes_skill_lifecycle(
    *,
    hermes_home: Path | str = DEFAULT_HERMES_HOME,
    hermes_config_path: Path | str | None = None,
    include_external_dirs: bool = True,
    now: datetime | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    archive_after_days: int = DEFAULT_ARCHIVE_AFTER_DAYS,
    negative_claim_ttl_days: int = DEFAULT_NEGATIVE_CLAIM_TTL_DAYS,
    telemetry_path: Path | str | None = DEFAULT_TELEMETRY_PATH,
) -> dict[str, Any]:
    """Passively audit Hermes skill lifecycle health from Jarvis.

    This intentionally does not mutate Hermes skills, .usage.json files, or archives.
    It gives Jarvis a source-untouched control surface until upstream Curator is
    available in the local Hermes checkout.
    """
    hermes_home = Path(hermes_home).expanduser()
    hermes_config_path = Path(hermes_config_path).expanduser() if hermes_config_path else hermes_home / "config.yaml"
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    roots: list[dict[str, str]] = _skill_roots(hermes_home, hermes_config_path, include_external_dirs)
    telemetry_index = _load_telemetry(telemetry_path)

    seen: set[Path] = set()
    entries: list[dict[str, Any]] = []
    summary = {"total_skills": 0, "active": 0, "stale": 0, "archived": 0, "pinned": 0, "negative_claim_revalidation": 0, "archive_candidates": 0}

    for root in roots:
        root_path = Path(root["path"]).expanduser()
        for skill_dir in _iter_skill_dirs(root_path):
            resolved = skill_dir.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            skill_md = skill_dir / "SKILL.md"
            usage = _read_usage(skill_dir, telemetry_index)
            last_used_at = _parse_dt(usage.get("last_used_at") or usage.get("last_successful_apply_at") or usage.get("last_viewed_at"))
            last_patched_at = _parse_dt(usage.get("last_patched_at"))
            last_signal_at = last_used_at or last_patched_at or _parse_dt(usage.get("created_at"))
            age_days = (now - last_signal_at).days if last_signal_at else None
            pinned = bool(usage.get("pinned"))
            state = _state_for(skill_dir=skill_dir, usage=usage, age_days=age_days, pinned=pinned, stale_after_days=stale_after_days, archive_after_days=archive_after_days)
            negative_claims = _negative_claims(skill_md, now=now, last_signal_at=last_patched_at or last_signal_at, ttl_days=negative_claim_ttl_days)

            recommendations: list[str] = []
            if pinned:
                recommended_action = "keep_pinned"
            elif state == "archived":
                recommended_action = "already_archived"
            elif age_days is not None and age_days >= archive_after_days:
                recommended_action = "archive_candidate"
                recommendations.append("archive_candidate")
            elif state == "stale":
                recommended_action = "stale_review"
                recommendations.append("stale_review")
            else:
                recommended_action = "keep_active"
            if negative_claims["revalidate"]:
                recommendations.append("negative_claim_revalidation")

            summary["total_skills"] += 1
            summary[state] += 1
            if pinned:
                summary["pinned"] += 1
            if recommended_action == "archive_candidate":
                summary["archive_candidates"] += 1
            if negative_claims["revalidate"]:
                summary["negative_claim_revalidation"] += 1

            entries.append({
                "name": _skill_name(skill_dir, skill_md),
                "path": str(skill_dir),
                "source": root["kind"],
                "state": state,
                "recommended_action": recommended_action,
                "recommendations": recommendations,
                "pinned": pinned,
                "age_days": age_days,
                "use_count": int(usage.get("use_count") or 0) if not usage.get("_invalid") else 0,
                "patch_count": int(usage.get("patch_count") or 0) if not usage.get("_invalid") else 0,
                "last_used_at": last_used_at.isoformat() if last_used_at else None,
                "last_patched_at": last_patched_at.isoformat() if last_patched_at else None,
                "usage_metadata_present": bool(usage) and not usage.get("_invalid"),
                "usage_metadata_source": usage.get("_source") if usage and not usage.get("_invalid") else None,
                "usage_metadata_invalid": bool(usage.get("_invalid")),
                "negative_claims": negative_claims,
            })

    entries.sort(key=lambda item: (item["state"] != "archived", item["recommended_action"], item["name"]))
    return {
        "ok": True,
        "contract": "Hermes agent + jinwang-jarvis",
        "mode": "passive_source_untouched_skill_lifecycle_audit",
        "generated_at": now.isoformat(),
        "hermes_home": str(hermes_home),
        "hermes_config_path": str(hermes_config_path),
        "telemetry_path": str(Path(telemetry_path).expanduser()) if telemetry_path else None,
        "thresholds": {
            "stale_after_days": stale_after_days,
            "archive_after_days": archive_after_days,
            "negative_claim_ttl_days": negative_claim_ttl_days,
        },
        "roots": roots,
        "summary": summary,
        "skills": entries,
    }
