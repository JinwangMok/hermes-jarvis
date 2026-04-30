from pathlib import Path

from jinwang_jarvis.wiki_semantic_lint import lint_wiki_semantics


def test_lint_wiki_semantics_reports_generated_and_durable_issues(tmp_path: Path):
    wiki = tmp_path / "wiki"
    generated = wiki / "queries" / "jinwang-jarvis-report.md"
    generated.parent.mkdir(parents=True)
    generated.write_text(
        """---
title: Generated
generated: true
authority: derived
---
# Generated
This is the source of truth.
Apply now for this opportunity.
""",
        encoding="utf-8",
    )
    durable = wiki / "entities" / "person.md"
    durable.parent.mkdir(parents=True)
    durable.write_text(
        """---
title: Person
sources: []
---
# Person
This must always be current.
""",
        encoding="utf-8",
    )

    result = lint_wiki_semantics(wiki)

    assert result["ok"] is False
    codes = [issue["code"] for issue in result["issues"]]
    assert "generated_metadata_missing" in codes
    assert "generated_canonical_claim" in codes
    assert "actionable_without_evidence" in codes
    assert "durable_sources_missing" in codes
    assert result["error_count"] == 3
    assert result["warning_count"] == 1


def test_lint_wiki_semantics_skips_raw_body_checks(tmp_path: Path):
    wiki = tmp_path / "wiki"
    raw = wiki / "raw" / "capture.md"
    raw.parent.mkdir(parents=True)
    raw.write_text("# Raw\nThis is the source of truth. Apply now without dates.", encoding="utf-8")

    result = lint_wiki_semantics(wiki)

    assert result == {"ok": True, "error_count": 0, "warning_count": 0, "issues": []}


def test_lint_wiki_semantics_warns_daily_report_missing_status(tmp_path: Path):
    wiki = tmp_path / "wiki"
    report = wiki / "reports" / "daily" / "2026-04-30.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        """---
title: Daily
generated: true
authority: derived
refresh_policy: overwrite
operational_source_of_truth: state/personal_intel.db
---
# Daily
Derived report with evidence.
""",
        encoding="utf-8",
    )

    result = lint_wiki_semantics(wiki)

    assert result["ok"] is True
    assert result["warning_count"] == 1
    assert result["issues"][0]["code"] == "generated_status_missing"


def test_lint_wiki_semantics_requires_generated_true_for_generated_paths(tmp_path: Path):
    wiki = tmp_path / "wiki"
    report = wiki / "reports" / "daily" / "2026-04-30.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        """---
title: Daily
generated: false
authority: derived
refresh_policy: overwrite
operational_source_of_truth: state/personal_intel.db
---
# Daily
## Status
- TL;DR: derived report with evidence.
""",
        encoding="utf-8",
    )

    result = lint_wiki_semantics(wiki)

    assert result["ok"] is False
    assert result["error_count"] == 1
    assert result["issues"][0]["code"] == "generated_flag_not_true"
