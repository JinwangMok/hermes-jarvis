from __future__ import annotations

import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_SAMPLE_LIBRARY_DIR = Path(os.environ.get(
    "JARVIS_STYLED_VOICE_SAMPLE_DIR",
    "~/workspace/jinwang-jarvis/data/styled-voice-samples",
)).expanduser()

AUDIO_EXTENSIONS = {".wav", ".ogg", ".oga", ".opus", ".m4a", ".mp3", ".flac", ".webm", ".aac"}
_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class VoiceProfile:
    profile: str
    person: str
    style: str
    path: Path
    sample_count: int
    samples: tuple[Path, ...]


def sanitize_label(label: str) -> str:
    cleaned = _SAFE_LABEL_RE.sub("-", (label or "").strip()).strip(".-_")
    if not cleaned:
        raise ValueError("label must contain at least one safe character")
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"unsafe label: {label!r}")
    return cleaned


def parse_profile(profile: str | None, *, person: str | None = None, style: str | None = None) -> tuple[str, str]:
    if profile:
        parts = [part for part in profile.strip().split("/") if part]
        if len(parts) > 2:
            raise ValueError("profile must be '<person>' or '<person>/<style>'")
        parsed_person = parts[0] if parts else "default"
        parsed_style = parts[1] if len(parts) == 2 else "default"
    else:
        parsed_person = person or "default"
        parsed_style = style or "default"
    return sanitize_label(parsed_person), sanitize_label(parsed_style or "default")


def profile_dir(library_dir: Path | str | None = None, profile: str | None = None, *, person: str | None = None, style: str | None = None) -> Path:
    base = Path(library_dir).expanduser() if library_dir else DEFAULT_SAMPLE_LIBRARY_DIR
    resolved_person, resolved_style = parse_profile(profile, person=person, style=style)
    return base / resolved_person / resolved_style


def _is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS and not path.name.startswith(".")


def collect_profile_audio(library_dir: Path | str | None = None, profile: str | None = None, *, person: str | None = None, style: str | None = None) -> list[Path]:
    target = profile_dir(library_dir, profile, person=person, style=style)
    files = sorted(path.resolve() for path in target.iterdir() if _is_audio_file(path)) if target.exists() else []

    # Compatibility with the shorthand Jinwang proposed: files directly under
    # <library>/<person> are usable when style defaults to 'default'.
    resolved_person, resolved_style = parse_profile(profile, person=person, style=style)
    if resolved_style == "default":
        direct_dir = (Path(library_dir).expanduser() if library_dir else DEFAULT_SAMPLE_LIBRARY_DIR) / resolved_person
        if direct_dir.exists():
            files.extend(path.resolve() for path in sorted(direct_dir.iterdir()) if _is_audio_file(path))
    return sorted(dict.fromkeys(files))


def add_samples(audio_paths: Sequence[Path | str], library_dir: Path | str | None = None, profile: str | None = None, *, person: str | None = None, style: str | None = None, copy: bool = True) -> dict:
    target = profile_dir(library_dir, profile, person=person, style=style)
    target.mkdir(parents=True, exist_ok=True)
    added: list[Path] = []
    for raw in audio_paths:
        source = Path(raw).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"audio file not found: {source}")
        if source.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError(f"unsupported audio extension: {source.suffix}")
        stem = sanitize_label(source.stem)
        destination = target / f"{stem}{source.suffix.lower()}"
        if destination.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            destination = target / f"{stem}-{stamp}{source.suffix.lower()}"
        if copy:
            shutil.copy2(source, destination)
        else:
            shutil.move(str(source), destination)
        added.append(destination.resolve())
    resolved_person, resolved_style = parse_profile(profile, person=person, style=style)
    return {
        "profile": f"{resolved_person}/{resolved_style}",
        "person": resolved_person,
        "style": resolved_style,
        "path": str(target.resolve()),
        "added": [str(path) for path in added],
        "sample_count": len(collect_profile_audio(library_dir, profile, person=person, style=style)),
    }


def list_profiles(library_dir: Path | str | None = None) -> list[dict]:
    base = Path(library_dir).expanduser() if library_dir else DEFAULT_SAMPLE_LIBRARY_DIR
    if not base.exists():
        return []
    profiles: list[VoiceProfile] = []
    for person_dir in sorted(path for path in base.iterdir() if path.is_dir() and not path.name.startswith(".")):
        direct_samples = tuple(path.resolve() for path in sorted(person_dir.iterdir()) if _is_audio_file(path))
        if direct_samples:
            profiles.append(VoiceProfile(
                profile=f"{person_dir.name}/default",
                person=person_dir.name,
                style="default",
                path=person_dir.resolve(),
                sample_count=len(direct_samples),
                samples=direct_samples,
            ))
        for style_dir in sorted(path for path in person_dir.iterdir() if path.is_dir() and not path.name.startswith(".")):
            samples = tuple(path.resolve() for path in sorted(style_dir.iterdir()) if _is_audio_file(path))
            if samples:
                profiles.append(VoiceProfile(
                    profile=f"{person_dir.name}/{style_dir.name}",
                    person=person_dir.name,
                    style=style_dir.name,
                    path=style_dir.resolve(),
                    sample_count=len(samples),
                    samples=samples,
                ))
    return [
        {**asdict(profile), "path": str(profile.path), "samples": [str(path) for path in profile.samples]}
        for profile in profiles
    ]


def init_library(library_dir: Path | str | None = None, profiles: Iterable[str] = ("default",)) -> dict:
    base = Path(library_dir).expanduser() if library_dir else DEFAULT_SAMPLE_LIBRARY_DIR
    created: list[str] = []
    for profile in profiles:
        path = profile_dir(base, profile)
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path.resolve()))
    return {"library_dir": str(base.resolve()), "created": created}
