from pathlib import Path

import pytest

from jinwang_jarvis.styled_voice_samples import add_samples, collect_profile_audio, list_profiles, parse_profile, profile_dir, sanitize_label


def test_parse_profile_defaults_style():
    assert parse_profile("jongwon") == ("jongwon", "default")
    assert parse_profile("jongwon/calm") == ("jongwon", "calm")


def test_sanitize_label_rejects_empty():
    with pytest.raises(ValueError):
        sanitize_label("///")


def test_profile_dir_uses_person_style_layout(tmp_path: Path):
    assert profile_dir(tmp_path, "jongwon/calm") == tmp_path / "jongwon" / "calm"
    assert profile_dir(tmp_path, "default") == tmp_path / "default" / "default"


def test_add_and_collect_samples_by_profile(tmp_path: Path):
    source = tmp_path / "upload one.wav"
    source.write_bytes(b"RIFF")

    result = add_samples([source], tmp_path / "library", "jongwon/calm")

    assert result["profile"] == "jongwon/calm"
    copied = Path(result["added"][0])
    assert copied.exists()
    assert copied.parent == tmp_path / "library" / "jongwon" / "calm"
    assert collect_profile_audio(tmp_path / "library", "jongwon/calm") == [copied]


def test_collect_default_style_also_accepts_files_directly_under_person_dir(tmp_path: Path):
    direct = tmp_path / "library" / "jongwon" / "sample.wav"
    direct.parent.mkdir(parents=True)
    direct.write_bytes(b"RIFF")

    assert collect_profile_audio(tmp_path / "library", "jongwon") == [direct.resolve()]


def test_list_profiles_reports_sample_counts(tmp_path: Path):
    sample = tmp_path / "src.wav"
    sample.write_bytes(b"RIFF")
    add_samples([sample], tmp_path / "library", "default")

    profiles = list_profiles(tmp_path / "library")

    assert profiles[0]["profile"] == "default/default"
    assert profiles[0]["sample_count"] == 1
