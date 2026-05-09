import json
import sqlite3
from pathlib import Path

from zeus_os.bootstrap import bootstrap_workspace
from zeus_os.config import load_pipeline_config
from zeus_os.mail_secretary import generate_mail_secretary_cases, review_mail_secretary_cases


def _config(tmp_path: Path):
    sender_map = tmp_path / "sender-map.md"
    sender_map.write_text("## Current members\n- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr\n", encoding="utf-8")
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(
        f"""
workspace_root: {tmp_path.as_posix()}
wiki_root: /home/jinwang/wiki
accounts:
  - smartx
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 50
  sent_folder_overrides: {{}}
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
  max_results: 5
classification:
  sender_map_path: {sender_map.as_posix()}
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord-origin
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: zeus-os
""",
        encoding="utf-8",
    )
    return load_pipeline_config(config_file)


def _insert_message(conn: sqlite3.Connection, *, message_id: str, folder_kind: str, subject: str, from_addr: str, to_addrs: str = "[]", body_path: str | None = None, snippet: str = ""):
    conn.execute(
        """
        INSERT INTO messages (
            message_id, account, folder_kind, thread_key, subject, from_addr, to_addrs,
            cc_addrs, self_role, interaction_role, sent_at, snippet, body_path, raw_json_path, is_seen, ingested_at
        ) VALUES (?, 'smartx', ?, ?, ?, ?, ?, '[]', 'other', 'direct', '2026-05-07T15:00:00+00:00', ?, ?, NULL, 0, '2999-01-01T00:00:00+00:00')
        """,
        (message_id, folder_kind, subject, subject.lower(), from_addr, to_addrs, snippet, body_path),
    )


def test_bootstrap_creates_mail_secretary_tables_and_dirs(tmp_path: Path):
    config = _config(tmp_path)
    bootstrap_workspace(config)
    bootstrap_workspace(config)

    assert (tmp_path / "data" / "secretary" / "runs").is_dir()
    assert (tmp_path / "data" / "secretary" / "drafts").is_dir()
    with sqlite3.connect(config.database_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"mail_secretary_cases", "mail_secretary_evidence", "mail_secretary_drafts"} <= tables
    assert {
        "idx_mail_secretary_cases_status_updated",
        "idx_mail_secretary_evidence_case",
        "idx_mail_secretary_drafts_case_status",
    } <= indexes


def test_secretary_triage_creates_action_ready_case_evidence_and_reply_draft(tmp_path: Path):
    config = _config(tmp_path)
    bootstrap_workspace(config)
    body_file = tmp_path / "data" / "mail-bodies" / "m1.txt"
    body_file.parent.mkdir(parents=True)
    body_file.write_text("김재현 엔지니어님이 데이터반 자료 확인과 회신을 요청했습니다. 내일까지 검토 후 답장 부탁드립니다.", encoding="utf-8")

    with sqlite3.connect(config.database_path) as conn:
        conn.execute("INSERT INTO sender_identities VALUES (?, ?, ?, ?, ?, ?)", ("jaehyun@example.com", "김재현", "engineer", "data-team", 40, "test"))
        _insert_message(conn, message_id="inbox-1", folder_kind="inbox", subject="데이터반 자료 확인 요청", from_addr="jaehyun@example.com", body_path=str(body_file.relative_to(tmp_path)))
        _insert_message(conn, message_id="sent-1", folder_kind="sent", subject="Re: 데이터반 자료 확인 요청", from_addr="jinwang@smartx.kr", to_addrs=json.dumps(["jaehyun@example.com"]))
        conn.execute("INSERT INTO message_labels VALUES (?, ?, ?, ?)", ("inbox-1", "direct-ask", 80.0, "{}"))
        conn.commit()

    result = generate_mail_secretary_cases(config, message_id="inbox-1", since_minutes=10, limit=5)

    assert result["case_count"] == 1
    assert result["draft_count"] == 1
    assert result["needs_approval_count"] == 1
    assert "[메일 행동 요청]" in result["approval_cards"][0]
    assert "과거 보낸메일 근거" in result["approval_cards"][0]

    with sqlite3.connect(config.database_path) as conn:
        case_rows = conn.execute("SELECT status, action_type, analysis_basis FROM mail_secretary_cases").fetchall()
        evidence_rows = conn.execute("SELECT evidence_kind FROM mail_secretary_evidence").fetchall()
        draft_rows = conn.execute("SELECT draft_type, external_effect, approval_required, artifact_file FROM mail_secretary_drafts").fetchall()
    assert case_rows == [("awaiting_approval", "reply", "body+subject")]
    assert ("sent_mail_history",) in evidence_rows
    assert draft_rows[0][0:3] == ("reply", "send_mail", 1)
    assert (tmp_path / draft_rows[0][3]).exists()


def test_secretary_triage_is_idempotent_and_review_renders_markdown(tmp_path: Path):
    config = _config(tmp_path)
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        _insert_message(conn, message_id="inbox-2", folder_kind="inbox", subject="Please review meeting agenda", from_addr="jongwon@smartx.kr", snippet="Please review and reply")
        conn.execute("INSERT INTO sender_identities VALUES (?, ?, ?, ?, ?, ?)", ("jongwon@smartx.kr", "JongWon Kim", "advisor", "smartx", 100, "test"))
        conn.execute("INSERT INTO message_labels VALUES (?, ?, ?, ?)", ("inbox-2", "advisor-request", 100.0, "{}"))
        conn.commit()

    generate_mail_secretary_cases(config, message_id="inbox-2", since_minutes=10, limit=5)
    generate_mail_secretary_cases(config, message_id="inbox-2", since_minutes=10, limit=5)

    with sqlite3.connect(config.database_path) as conn:
        assert conn.execute("SELECT count(*) FROM mail_secretary_cases").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM mail_secretary_drafts").fetchone()[0] == 1

    review = review_mail_secretary_cases(config, fmt="markdown")
    assert review["case_count"] == 1
    assert "[메일 행동 요청]" in review["markdown"]
    assert "승인 필요" in review["markdown"]


def test_secretary_triage_covers_calendar_task_noise_and_risk_paths(tmp_path: Path):
    config = _config(tmp_path)
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        _insert_message(conn, message_id="calendar-1", folder_kind="inbox", subject="내일 회의 참석 일정 확인", from_addr="staff@example.com", snippet="내일 미팅 참석 가능 여부 확인 부탁드립니다.")
        conn.execute("INSERT INTO message_labels VALUES (?, ?, ?, ?)", ("calendar-1", "meeting", 90.0, "{}"))
        _insert_message(conn, message_id="task-1", folder_kind="inbox", subject="자료 제출 마감 안내", from_addr="admin@example.com", snippet="금요일까지 신청서 제출 부탁드립니다.")
        _insert_message(conn, message_id="noise-1", folder_kind="inbox", subject="newsletter 프로모션", from_addr="promo@example.com", snippet="광고 newsletter")
        _insert_message(conn, message_id="risk-1", folder_kind="inbox", subject="계약 견적 검토 요청", from_addr="vendor@example.com", snippet="구매 계약과 견적 확정 요청드립니다.")
        conn.commit()

    expectations = {
        "calendar-1": ("calendar", "none", "awaiting_approval"),
        "task-1": ("task", "low", "awaiting_approval"),
        "noise-1": ("ignore", "none", "suppressed"),
        "risk-1": ("reply", "high", "awaiting_approval"),
    }
    for message_id in expectations:
        generate_mail_secretary_cases(config, message_id=message_id, since_minutes=10, limit=5)

    with sqlite3.connect(config.database_path) as conn:
        rows = conn.execute("SELECT source_message_id, action_type, risk_level, status FROM mail_secretary_cases").fetchall()
        drafts = conn.execute("SELECT d.external_effect, d.approval_required FROM mail_secretary_drafts d JOIN mail_secretary_cases c ON c.case_id = d.case_id WHERE c.source_message_id IN ('calendar-1', 'task-1', 'risk-1')").fetchall()
    assert {row[0]: row[1:] for row in rows} == expectations
    assert set(drafts) == {("create_calendar", 1), ("create_task", 1), ("send_mail", 1)}


def test_secretary_dry_run_writes_artifact_but_no_db_rows_and_empty_review(tmp_path: Path):
    config = _config(tmp_path)
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        _insert_message(conn, message_id="dry-1", folder_kind="inbox", subject="Please reply", from_addr="person@example.com", snippet="Please reply after review")
        conn.commit()

    result = generate_mail_secretary_cases(config, message_id="dry-1", since_minutes=10, limit=5, dry_run=True)
    assert result["case_count"] == 1
    assert result["needs_approval_count"] == 1
    assert result["artifact_path"].exists()
    assert result["cases"][0]["approval_card_md"]
    run_artifact = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert run_artifact["cases"][0]["approval_card_md"] == result["cases"][0]["approval_card_md"]
    assert run_artifact["cases"][0]["case_id"] == result["cases"][0]["case_id"]
    assert not list((tmp_path / "data" / "secretary" / "drafts").glob("*"))

    with sqlite3.connect(config.database_path) as conn:
        assert conn.execute("SELECT count(*) FROM mail_secretary_cases").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM mail_secretary_drafts").fetchone()[0] == 0

    review = review_mail_secretary_cases(config, fmt="markdown")
    assert review["case_count"] == 0
    assert review["markdown"] == "신규로 허락 요청할 메일 case 없음."


def test_secretary_refuses_absolute_body_path_outside_workspace(tmp_path: Path):
    config = _config(tmp_path)
    bootstrap_workspace(config)
    outside_body = tmp_path.parent / f"{tmp_path.name}-outside-body.txt"
    outside_body.write_text("Please reply with the leaked outside workspace body secret-token=outside", encoding="utf-8")
    try:
        with sqlite3.connect(config.database_path) as conn:
            _insert_message(
                conn,
                message_id="outside-body-1",
                folder_kind="inbox",
                subject="Please review",
                from_addr="person@example.com",
                body_path=str(outside_body),
                snippet="Please reply based on the visible snippet",
            )
            conn.commit()

        result = generate_mail_secretary_cases(config, message_id="outside-body-1", since_minutes=10, limit=5)

        assert result["cases"][0]["analysis_basis"] == "subject+snippet/body-outside-workspace"
        assert "outside workspace body" not in result["artifact_path"].read_text(encoding="utf-8")
        with sqlite3.connect(config.database_path) as conn:
            assert conn.execute("SELECT analysis_basis FROM mail_secretary_cases").fetchone()[0] == "subject+snippet/body-outside-workspace"
    finally:
        outside_body.unlink(missing_ok=True)


def test_secretary_redacts_secrets_from_reported_and_persisted_outputs(tmp_path: Path):
    config = _config(tmp_path)
    bootstrap_workspace(config)
    body_file = tmp_path / "data" / "mail-bodies" / "secret.txt"
    body_file.parent.mkdir(parents=True)
    body_file.write_text("Please reply. Bearer abcdefghijklmnopqrstuvwxyz123456 and token: body-token-12345", encoding="utf-8")
    with sqlite3.connect(config.database_path) as conn:
        _insert_message(
            conn,
            message_id="secret-1",
            folder_kind="inbox",
            subject="Please reply password=hunter2 sk-testSECRET1234567890",
            from_addr="person@example.com",
            body_path=str(body_file.relative_to(tmp_path)),
            snippet="api key: snippet-key-12345 and secret=snippet-secret-12345",
        )
        conn.commit()

    result = generate_mail_secretary_cases(config, message_id="secret-1", since_minutes=10, limit=5)

    with sqlite3.connect(config.database_path) as conn:
        persisted_text = "\n".join(
            str(value or "")
            for row in conn.execute("SELECT meaning_summary, risk_summary, approval_card_md FROM mail_secretary_cases").fetchall()
            for value in row
        )
        draft_row = conn.execute("SELECT title, body_md, artifact_file FROM mail_secretary_drafts").fetchone()
        persisted_text += "\n" + "\n".join(str(value or "") for value in draft_row[:2])
    artifact_text = result["artifact_path"].read_text(encoding="utf-8")
    draft_artifact_text = (tmp_path / draft_row[2]).read_text(encoding="utf-8")
    reported_text = json.dumps(result, ensure_ascii=False, default=str)
    combined = "\n".join([persisted_text, artifact_text, draft_artifact_text, reported_text])

    for leaked in ["hunter2", "sk-testSECRET1234567890", "snippet-key-12345", "snippet-secret-12345", "abcdefghijklmnopqrstuvwxyz123456", "body-token-12345"]:
        assert leaked not in combined
    assert "[REDACTED]" in combined
