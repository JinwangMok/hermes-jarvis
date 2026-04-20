import json
import sqlite3
from datetime import datetime
from pathlib import Path

from jinwang_jarvis.bootstrap import bootstrap_workspace
from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.proposals import derive_message_scores, extract_candidate_event, generate_proposals, MessageContext


SENDER_MAP = """
## Current members
- Professor | 김종원(JongWon Kim) | jongwon@smartx.kr
- Ph.D. Student | 목진왕(JinWang Mok) | jinwang@smartx.kr / jinwangmok@gmail.com
"""


def _config_text(root: Path) -> str:
    return """
workspace_root: {root}
wiki_root: /home/jinwang/wiki
accounts:
  - personal
  - smartx
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 50
  sent_folder_overrides: {{}}
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
  max_results: 5
  time_min: 2026-04-19T00:00:00+09:00
  time_max: 2026-05-19T00:00:00+09:00
classification:
  sender_map_path: {sender_map}
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord-origin
reproducibility:
  packaging: pyproject
  config_format: yaml
  project_name: jinwang-jarvis
""".format(root=root.as_posix(), sender_map=(root / 'sender-map.md').as_posix())


def _load_config(tmp_path: Path):
    (tmp_path / "sender-map.md").write_text(SENDER_MAP, encoding="utf-8")
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(_config_text(tmp_path), encoding="utf-8")
    return load_pipeline_config(config_file)


def _insert_message(conn: sqlite3.Connection, **kwargs):
    conn.execute(
        """
        INSERT INTO messages (
            message_id, account, folder_kind, thread_key, subject, from_addr, to_addrs,
            cc_addrs, sent_at, snippet, body_path, raw_json_path, is_seen, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kwargs["message_id"],
            kwargs.get("account", "smartx"),
            kwargs.get("folder_kind", "inbox"),
            None,
            kwargs.get("subject"),
            kwargs.get("from_addr"),
            kwargs.get("to_addrs"),
            None,
            kwargs.get("sent_at"),
            None,
            None,
            None,
            kwargs.get("is_seen", 0),
            kwargs.get("ingested_at", "2026-04-19T00:00:00+00:00"),
        ),
    )


def _insert_label(conn: sqlite3.Connection, message_id: str, label: str, score: float):
    conn.execute(
        "INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)",
        (message_id, label, score, json.dumps({"seed": label}, ensure_ascii=False)),
    )


def _insert_identity(conn: sqlite3.Connection, email: str, role: str, priority_base: int):
    conn.execute(
        "INSERT INTO sender_identities (email, display_name, role, organization, priority_base, source_note) VALUES (?, ?, ?, ?, ?, ?)",
        (email, email, role, "smartx", priority_base, "test"),
    )


def _insert_watchlist(conn: sqlite3.Connection, **kwargs):
    conn.execute(
        """
        INSERT INTO message_watchlist (
            source_message_id, title, watch_kind, promotion_score, first_seen_at,
            last_seen_at, seen_count, latest_reason_json, latest_artifact_file, wiki_note_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kwargs["source_message_id"],
            kwargs.get("title", "watch item"),
            kwargs.get("watch_kind", "promotion-candidate"),
            kwargs.get("promotion_score", 0.55),
            kwargs.get("first_seen_at", "2026-04-10T00:00:00+00:00"),
            kwargs.get("last_seen_at", "2026-04-18T00:00:00+00:00"),
            kwargs.get("seen_count", 2),
            kwargs.get("latest_reason_json", json.dumps({"reason": {"kind": "low-confidence"}}, ensure_ascii=False)),
            kwargs.get("latest_artifact_file", "watchlist-test.json"),
            kwargs.get("wiki_note_path"),
        ),
    )


def test_derive_message_scores_prioritizes_advisor_meeting_requests():
    advisor_message = MessageContext(
        message_id="m1",
        account="smartx",
        folder_kind="inbox",
        subject="Please review meeting agenda for 2026-04-21 13:00",
        from_addr="jongwon@smartx.kr",
        sent_at="2026-04-19T00:00:00+00:00",
        role="advisor",
        priority_base=100,
        labels=(
            {"label": "advisor-request", "score": 100.0, "reason": {}},
            {"label": "meeting", "score": 40.0, "reason": {}},
        ),
    )
    newsletter_message = MessageContext(
        message_id="m2",
        account="personal",
        folder_kind="inbox",
        subject="Vendor promo newsletter security alert",
        from_addr="vendor@example.test",
        sent_at="2026-04-19T00:00:00+00:00",
        role="external",
        priority_base=0,
        labels=(
            {"label": "promotional-reference", "score": 15.0, "reason": {}},
            {"label": "security-routine", "score": 20.0, "reason": {}},
        ),
    )

    advisor_scores = derive_message_scores(advisor_message)
    newsletter_scores = derive_message_scores(newsletter_message)
    candidate = extract_candidate_event(advisor_message, advisor_scores)

    assert advisor_scores["priority"] > 0.9
    assert advisor_scores["action"] > 0.8
    assert advisor_scores["calendar"] > 0.7
    assert newsletter_scores["noise"] > advisor_scores["noise"]
    assert candidate is not None
    assert candidate.start_ts == "2026-04-21T13:00:00+09:00"


def test_generate_proposals_persists_action_signals_and_artifact(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "jongwon@smartx.kr", "advisor", 100)
        _insert_identity(conn, "jinwang@smartx.kr", "self", 90)
        _insert_message(
            conn,
            message_id="inbox-1",
            account="smartx",
            folder_kind="inbox",
            subject="Please review meeting agenda 2026-04-21 13:00",
            from_addr="jongwon@smartx.kr",
            sent_at="2026-04-19T09:00:00+09:00",
        )
        _insert_message(
            conn,
            message_id="sent-1",
            account="smartx",
            folder_kind="sent",
            subject="Re: Please review meeting agenda 2026-04-21 13:00",
            from_addr="jinwang@smartx.kr",
            sent_at="2026-04-19T10:00:00+09:00",
        )
        _insert_label(conn, "inbox-1", "advisor-request", 100.0)
        _insert_label(conn, "inbox-1", "meeting", 40.0)
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 1
    assert result["action_signal_count"] >= 1
    assert result["artifact_path"].exists()

    with sqlite3.connect(config.database_path) as conn:
        signal_rows = conn.execute(
            "SELECT source_message_id, signal_type, evidence_message_id FROM action_signals ORDER BY id"
        ).fetchall()
        proposal_rows = conn.execute(
            "SELECT source_message_id, title, start_ts, status, reason_json FROM event_proposals"
        ).fetchall()

    assert ("inbox-1", "reply_detected", "sent-1") in signal_rows
    assert len(proposal_rows) == 1
    assert proposal_rows[0][0] == "inbox-1"
    assert proposal_rows[0][3] == "proposed"
    reason = json.loads(proposal_rows[0][4])
    assert reason["scores"]["priority"] > 0.8
    assert reason["scores"]["calendar"] > 0.7

    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["proposal_count"] == 1
    assert artifact_payload["proposals"][0]["title"] == "Please review meeting agenda 2026-04-21 13:00"


def test_generate_proposals_suppresses_existing_calendar_duplicates(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "jongwon@smartx.kr", "advisor", 100)
        _insert_message(
            conn,
            message_id="inbox-1",
            account="smartx",
            folder_kind="inbox",
            subject="Lab meeting 2026-04-21 13:00",
            from_addr="jongwon@smartx.kr",
            sent_at="2026-04-19T09:00:00+09:00",
        )
        _insert_label(conn, "inbox-1", "meeting", 40.0)
        conn.execute(
            """
            INSERT INTO calendar_events (
                event_id, calendar_id, summary, status, start_ts, end_ts, location,
                html_link, dedup_key, raw_json_path, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evt-1",
                "primary",
                "Lab meeting 2026-04-21 13:00",
                "confirmed",
                "2026-04-21T13:00:00+09:00",
                "2026-04-21T14:00:00+09:00",
                None,
                None,
                "lab meeting 2026-04-21 13:00|2026-04-21t13:00:00+09:00",
                None,
                "2026-04-19T00:00:00+00:00",
            ),
        )
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 0
    assert result["suppressed_count"] == 1

    with sqlite3.connect(config.database_path) as conn:
        proposal_count = conn.execute("SELECT COUNT(*) FROM event_proposals").fetchone()[0]
    assert proposal_count == 0

    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["suppressed"][0]["reason"]["kind"] == "calendar-dedup-key"


def test_generate_proposals_suppresses_advisor_fyi_promotional_subjects(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "jongwon@smartx.kr", "advisor", 100)
        _insert_message(
            conn,
            message_id="inbox-fyi",
            account="smartx",
            folder_kind="inbox",
            subject="초대장] 2026년도 인공지능 챔피언 대회 사업설명회에 여러분을 초대합니다!",
            from_addr="jongwon@smartx.kr",
            sent_at="2026-04-19T09:00:00+09:00",
        )
        _insert_label(conn, "inbox-fyi", "advisor-fyi", 35.0)
        _insert_label(conn, "inbox-fyi", "work-account", 10.0)
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 0
    with sqlite3.connect(config.database_path) as conn:
        proposal_count = conn.execute("SELECT COUNT(*) FROM event_proposals").fetchone()[0]
    assert proposal_count == 0


def test_extract_candidate_event_handles_two_digit_year_without_false_month_match():
    message = MessageContext(
        message_id="m3",
        account="smartx",
        folder_kind="inbox",
        subject="[NetAI System] 시스템팀 미팅 자료 공유드립니다. (26-04-19)",
        from_addr="member@smartx.kr",
        sent_at="2026-04-19T00:00:00+00:00",
        role="lab-member",
        priority_base=20,
        labels=(
            {"label": "meeting", "score": 40.0, "reason": {}},
        ),
    )

    scores = derive_message_scores(message)
    candidate = extract_candidate_event(message, scores)

    assert candidate is not None
    assert candidate.start_ts == "2026-04-19T09:00:00+09:00"


def test_extract_candidate_event_anchors_yearless_date_to_message_sent_at():
    message = MessageContext(
        message_id="m-yearless-anchor",
        account="personal",
        folder_kind="inbox",
        subject="이주의 미팅 (7/17~7/21)",
        from_addr="seungjun@gist.ac.kr",
        sent_at="2023-07-14T06:45:00+00:00",
        role="external",
        priority_base=0,
        labels=(
            {"label": "meeting", "score": 40.0, "reason": {}},
        ),
    )

    scores = derive_message_scores(message)
    candidate = extract_candidate_event(message, scores)

    assert candidate is not None
    assert candidate.start_ts == "2023-07-17T09:00:00+09:00"


def test_generate_proposals_suppresses_historical_yearless_dates_using_sent_at_anchor(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_message(
            conn,
            message_id="historical-1",
            account="personal",
            folder_kind="inbox",
            subject="이주의 미팅 (7/17~7/21)",
            from_addr="seungjun@gist.ac.kr",
            sent_at="2023-07-14T06:45:00+00:00",
        )
        _insert_label(conn, "historical-1", "meeting", 40.0)
        conn.commit()

    result = generate_proposals(config, as_of=datetime.fromisoformat("2026-04-20T00:00:00+00:00"))

    assert result["proposal_count"] == 0
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["suppressed"][0]["source_message_id"] == "historical-1"
    assert artifact_payload["suppressed"][0]["details"]["suppression"]["kind"] == "policy-past-event"


def test_generate_proposals_suppresses_promotional_dateless_items(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "jongwon@smartx.kr", "advisor", 100)
        _insert_message(
            conn,
            message_id="promo-1",
            account="smartx",
            folder_kind="inbox",
            subject="Join 'Running Wasm Inside Your Storage Cluster with CSI and Gateway API' as a speaker",
            from_addr="partner@example.org",
            sent_at="2026-04-01T09:00:00+09:00",
        )
        _insert_label(conn, "promo-1", "promotional-reference", 15.0)
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 0
    assert result["suppressed_count"] == 0


def test_generate_proposals_resurrects_watchlist_item_when_seen_repeatedly_and_date_is_near(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "member@smartx.kr", "lab-member", 20)
        _insert_message(
            conn,
            message_id="watch-near",
            account="smartx",
            folder_kind="inbox",
            subject="Lab sync 2026-04-22 14:00",
            from_addr="member@smartx.kr",
            sent_at="2026-04-19T09:00:00+09:00",
        )
        _insert_label(conn, "watch-near", "lab", 30.0)
        _insert_label(conn, "watch-near", "work-account", 10.0)
        _insert_watchlist(conn, source_message_id="watch-near", title="Lab sync 2026-04-22 14:00", seen_count=3)
        conn.commit()

    result = generate_proposals(config, as_of=datetime.fromisoformat("2026-04-20T00:00:00+00:00"))

    assert result["proposal_count"] == 1
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["proposals"][0]["source_message_id"] == "watch-near"
    assert artifact_payload["proposals"][0]["reason"]["watchlist"]["resurrected"] is True


def test_generate_proposals_resurrects_reply_backed_watchlist_item(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "jongwon@smartx.kr", "advisor", 100)
        _insert_identity(conn, "jinwang@smartx.kr", "self", 90)
        _insert_message(
            conn,
            message_id="watch-reply",
            account="smartx",
            folder_kind="inbox",
            subject="Re: 장비 구매 관련 검토 요청",
            from_addr="jongwon@smartx.kr",
            sent_at="2026-04-19T09:00:00+09:00",
        )
        _insert_message(
            conn,
            message_id="watch-reply-sent",
            account="smartx",
            folder_kind="sent",
            subject="Re: 장비 구매 관련 검토 요청",
            from_addr="jinwang@smartx.kr",
            sent_at="2026-04-19T10:00:00+09:00",
        )
        _insert_label(conn, "watch-reply", "advisor-fyi", 35.0)
        _insert_label(conn, "watch-reply", "work-account", 10.0)
        _insert_watchlist(conn, source_message_id="watch-reply", watch_kind="reply-backed-candidate", seen_count=2)
        conn.commit()

    result = generate_proposals(config, as_of=datetime.fromisoformat("2026-04-20T00:00:00+00:00"))

    assert result["proposal_count"] == 1
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    proposal = artifact_payload["proposals"][0]
    assert proposal["source_message_id"] == "watch-reply"
    assert proposal["reason"]["watchlist"]["resurrected"] is True


def test_generate_proposals_suppresses_external_online_seminar_invites(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_message(
            conn,
            message_id="seminar-1",
            account="smartx",
            folder_kind="inbox",
            subject="[OSIA] 실환경 로보틱스를 위한 VLA 기술 동향(2026.3.31.(화), 온라인(Zoom))",
            from_addr="osia@osia.or.kr",
            sent_at="2026-03-23T09:39:00+09:00",
        )
        _insert_label(conn, "seminar-1", "meeting", 40.0)
        _insert_label(conn, "seminar-1", "work-account", 10.0)
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 0
    assert result["suppressed_count"] == 1
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["suppressed"][0]["reason"]["kind"] == "low-confidence"


def test_generate_proposals_suppresses_conference_speaker_reminders(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "jongwon@smartx.kr", "advisor", 100)
        _insert_message(
            conn,
            message_id="speaker-1",
            account="smartx",
            folder_kind="inbox",
            subject="🇯🇵 Reminder: Speak at KubeCon + CloudNativeCon Japan!",
            from_addr="jongwon@smartx.kr",
            sent_at="2026-03-17T20:09:00+09:00",
        )
        _insert_label(conn, "speaker-1", "advisor-request", 70.0)
        _insert_label(conn, "speaker-1", "work-account", 10.0)
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 0
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["suppressed"][0]["details"]["suppression"]["kind"] == "policy-promotional-subject"


def test_generate_proposals_suppresses_mandatory_education_notices(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_message(
            conn,
            message_id="edu-1",
            account="personal",
            folder_kind="inbox",
            subject="FW: [법정의무교육] 2026 대학(원)생 봄학기 폭력예방교육 안내 (2026.4.20.~ 5.26.)",
            from_addr="jinwangmok@gm.gist.ac.kr",
            sent_at="2026-04-19T23:31:00+00:00",
        )
        _insert_label(conn, "edu-1", "work-account", 10.0)
        conn.commit()

    result = generate_proposals(config, as_of=datetime.fromisoformat("2026-04-20T00:00:00+00:00"))

    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    if result["proposal_count"] == 1:
        assert artifact_payload["proposals"][0]["source_message_id"] == "edu-1"
    else:
        assert artifact_payload["suppressed"][0]["source_message_id"] == "edu-1"
        suppression = artifact_payload["suppressed"][0]["details"].get("suppression")
        assert suppression is None or suppression["kind"] != "policy-promotional-subject"


def test_generate_proposals_suppresses_past_dated_events(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_message(
            conn,
            message_id="past-1",
            account="smartx",
            folder_kind="inbox",
            subject="[산자부E2E][데이터협의체] 6차 데이터협의체 회의 개별 안내 (4/2 13:30~15:30, 온라인)",
            from_addr="jey.kang@smartx.kr",
            sent_at="2026-03-27T06:43:00+09:00",
        )
        _insert_label(conn, "past-1", "lab", 30.0)
        _insert_label(conn, "past-1", "work-account", 10.0)
        conn.commit()

    result = generate_proposals(config, as_of=datetime.fromisoformat("2026-04-20T00:00:00+00:00"))

    assert result["proposal_count"] == 0
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["suppressed"][0]["details"]["suppression"]["kind"] == "policy-past-event"


def test_generate_proposals_suppresses_replied_reporting_threads(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "jongwon@smartx.kr", "advisor", 100)
        _insert_identity(conn, "jinwang@smartx.kr", "self", 90)
        _insert_message(
            conn,
            message_id="report-inbox",
            account="smartx",
            folder_kind="inbox",
            subject="Re: [산자부 E2E 과제] 장비 구매 관련 보고드립니다.",
            from_addr="jongwon@smartx.kr",
            sent_at="2026-04-03T20:12:00+09:00",
        )
        _insert_message(
            conn,
            message_id="report-reply",
            account="smartx",
            folder_kind="sent",
            subject="Re: [산자부 E2E 과제] 장비 구매 관련 보고드립니다.",
            from_addr="jinwang@smartx.kr",
            sent_at="2026-04-03T21:00:00+09:00",
        )
        _insert_label(conn, "report-inbox", "advisor-request", 70.0)
        _insert_label(conn, "report-inbox", "work-account", 10.0)
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 0
    assert result["suppressed_count"] == 1
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["suppressed"][0]["reason"]["kind"] == "low-confidence"


def test_generate_proposals_suppresses_forwarded_registration_admin_threads(tmp_path: Path):
    config = _load_config(tmp_path)
    bootstrap_workspace(config)

    with sqlite3.connect(config.database_path) as conn:
        _insert_identity(conn, "member@gist.ac.kr", "lab-member", 20)
        _insert_message(
            conn,
            message_id="admin-forward",
            account="smartx",
            folder_kind="inbox",
            subject="FW: VISITOR 내용추가_[ITRC 인재양성대전 2026 준비위원회_출판발송분과] 사전등록자 조사 요청 (~3/30까지)",
            from_addr="member@gist.ac.kr",
            sent_at="2026-03-24T14:29:00+09:00",
        )
        _insert_label(conn, "admin-forward", "lab", 30.0)
        _insert_label(conn, "admin-forward", "work-account", 10.0)
        conn.commit()

    result = generate_proposals(config)

    assert result["proposal_count"] == 0
    assert result["suppressed_count"] == 1
    artifact_payload = json.loads(result["artifact_path"].read_text(encoding="utf-8"))
    assert artifact_payload["suppressed"][0]["reason"]["kind"] == "low-confidence"
