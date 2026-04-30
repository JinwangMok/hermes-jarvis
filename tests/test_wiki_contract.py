from jinwang_jarvis.wiki_contract import EvidenceRef, redact_obvious_secrets, render_evidence_line, render_status_block, stable_source_hash


def test_stable_source_hash_is_deterministic_for_dict_order():
    assert stable_source_hash({"b": 2, "a": [1, "한글"]}) == stable_source_hash({"a": [1, "한글"], "b": 2})


def test_render_evidence_line_includes_optional_fields_and_redacts_secrets():
    line = render_evidence_line(
        "token=abc123",
        EvidenceRef(
            source_id="message-password=hunter2",
            source_kind="mail",
            source_url="https://example.com/item?api_key=secret-value",
            source_hash="hash123",
            observed_at="2026-04-30",
            confidence=0.876,
        ),
    )
    assert "token=[REDACTED]" in line
    assert "message-password=[REDACTED]" in line
    assert "api_key=[REDACTED]" in line
    assert "hash=hash123" in line
    assert "observed_at=2026-04-30" in line
    assert "confidence=0.88" in line


def test_redact_obvious_secrets_handles_uppercase_variants():
    assert redact_obvious_secrets("PASSWORD=abc TOKEN:xyz secret=value api_key=123") == "PASSWORD=[REDACTED] TOKEN:[REDACTED] secret=[REDACTED] api_key=[REDACTED]"


def test_render_status_block_has_stable_order():
    lines = render_status_block(
        tldr="candidate count password=hidden",
        current_status="derived watchlist; not canonical",
        last_verified="2026-04-30",
        evidence_coverage="SQLite and artifact",
        open_questions="human review",
    )
    assert lines == [
        "## Status",
        "- TL;DR: candidate count password=[REDACTED]",
        "- Current status: derived watchlist; not canonical",
        "- Last verified: 2026-04-30",
        "- Evidence coverage: SQLite and artifact",
        "- Open questions: human review",
    ]
