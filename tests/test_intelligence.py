import json
from datetime import UTC, datetime
from pathlib import Path

from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.intelligence import (
    _backfill_message_participant_cache,
    _build_education_cv_sections,
    _build_education_memory_records,
    _build_recent_action_alerts,
    _classify_jongwon_context,
    _get_cached_message_participants,
    _infer_interaction_chains,
    _parse_participant_headers,
    _systematic_backfill_message_participant_cache,
    collect_knowledge_mail,
    generate_daily_intelligence_report,
)


class FakeKnowledgeRunner:
    def __init__(self):
        self.commands = []

    def __call__(self, args):
        self.commands.append(args)
        key = tuple(args)
        responses = {
            ("himalaya", "folder", "list", "-a", "personal"): "| NAME | DESC |\n|------|------|\n| INBOX | \\HasNoChildren |\n| [Gmail]/전체보관함 | \\HasNoChildren, \\All |\n| [Gmail]/보낸편지함 | \\HasNoChildren, \\Sent |\n",
            (
                "himalaya", "envelope", "list", "-a", "personal", "--folder", "[Gmail]/전체보관함",
                "--page", "1", "--page-size", "100", "--output", "json",
            ): '[{"id":"201","flags":[],"subject":"AI agent meetup registration open","from":{"name":"Events","addr":"events@example.org"},"to":{"name":null,"addr":"you@example.com"},"date":"2026-04-19 10:00+00:00","has_attachment":false},{"id":"202","flags":[],"subject":"Global market update: oil and inflation","from":{"name":"News","addr":"news@example.org"},"to":{"name":null,"addr":"you@example.com"},"date":"2026-04-18 10:00+00:00","has_attachment":false},{"id":"203","flags":[],"subject":"HERMES TEST GIST-FORWARD STATIC-001","from":{"name":null,"addr":"you@example.com"},"to":{"name":null,"addr":"you@example.com"},"date":"2026-04-19 11:00+00:00","has_attachment":false},{"id":"204","flags":[],"subject":"Random low-signal general note","from":{"name":"Misc","addr":"misc@example.org"},"to":{"name":null,"addr":"you@example.com"},"date":"2026-04-18 09:00+00:00","has_attachment":false}]',
            (
                "himalaya", "envelope", "list", "-a", "personal", "--folder", "[Gmail]/전체보관함",
                "--page", "2", "--page-size", "100", "--output", "json",
            ): '[]',
        }
        try:
            return responses[key]
        except KeyError as exc:
            raise AssertionError(f"unexpected command: {args}") from exc


def _write_config(root: Path) -> Path:
    config_file = root / "pipeline.yaml"
    config_file.write_text(
        """
workspace_root: {root}
wiki_root: {wiki}
accounts:
  - personal
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 50
  sent_folder_overrides: {{}}
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
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
""".format(root=root.as_posix(), wiki=(root / 'wiki').as_posix()),
        encoding="utf-8",
    )
    return config_file


def test_infer_interaction_chains_marks_pending_replied_and_follow_up():
    rows = [
        {"knowledge_id": "1", "subject": "Please review architecture", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "review-request", "sent_at": "2026-04-10T10:00:00+00:00", "message_id_header": "<m1>", "in_reply_to": None, "references": []},
        {"knowledge_id": "2", "subject": "Re: Please review architecture", "from_addr": "me@example.com", "to_addr": "boss@example.com", "self_role": "sent-by-me", "interaction_role": "status-reply", "sent_at": "2026-04-10T12:00:00+00:00", "message_id_header": "<m2>", "in_reply_to": "<m1>", "references": ["<m1>"]},
        {"knowledge_id": "3", "subject": "Need update on budget", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-11T10:00:00+00:00", "message_id_header": "<m3>", "in_reply_to": None, "references": []},
        {"knowledge_id": "4", "subject": "Re: Need update on budget", "from_addr": "me@example.com", "to_addr": "boss@example.com", "self_role": "sent-by-me", "interaction_role": "status-reply", "sent_at": "2026-04-11T11:00:00+00:00", "message_id_header": "<m4>", "in_reply_to": "<m3>", "references": ["<m3>"]},
        {"knowledge_id": "5", "subject": "Budget follow-up question", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-11T12:00:00+00:00", "message_id_header": "<m5>", "in_reply_to": "<m4>", "references": ["<m3>", "<m4>"]},
        {"knowledge_id": "6", "subject": "Submit draft today", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-12T10:00:00+00:00", "message_id_header": "<m6>", "in_reply_to": None, "references": []},
        {"knowledge_id": "7", "subject": "[SmartX Info] infra weekly", "from_addr": "info@smartx.kr", "to_addr": "info@smartx.kr", "self_role": "other", "interaction_role": "broadcast", "sent_at": "2026-04-12T09:00:00+00:00", "message_id_header": "<m7>", "in_reply_to": None, "references": []},
    ]
    chains = _infer_interaction_chains(rows)
    by_subject = {item["latest_subject"]: item for item in chains}
    assert by_subject["Re: Please review architecture"]["state"] == "waiting-on-others"
    assert by_subject["Budget follow-up question"]["state"] == "follow-up-pending"
    assert by_subject["Submit draft today"]["state"] == "waiting-on-me"
    assert "[SmartX Info] infra weekly" not in by_subject


def test_parse_participant_headers_extracts_to_cc_reply_to_and_references():
    raw = b"""From: sender@example.com\nTo: me@example.com, team@example.com\nCc: boss@example.com\nReply-To: reply@example.com\nDelivered-To: me@example.com\nMessage-ID: <msg-1@example.com>\nIn-Reply-To: <msg-0@example.com>\nReferences: <a@example.com> <b@example.com>\nSubject: test\n\nbody\n"""
    parsed = _parse_participant_headers(raw)
    assert parsed["to"] == ["me@example.com", "team@example.com"]
    assert parsed["cc"] == ["boss@example.com"]
    assert parsed["reply_to"] == ["reply@example.com"]
    assert parsed["delivered_to"] == "me@example.com"
    assert parsed["message_id"] == "<msg-1@example.com>"
    assert parsed["in_reply_to"] == "<msg-0@example.com>"
    assert parsed["references"] == ["<a@example.com>", "<b@example.com>"]


def test_cached_message_participants_roundtrip(tmp_path: Path):
    from jinwang_jarvis.bootstrap import bootstrap_workspace
    from jinwang_jarvis.config import load_pipeline_config
    import sqlite3

    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO message_participant_cache (message_id, account, folder_name, source_id, to_addrs_json, cc_addrs_json, reply_to_addrs_json, delivered_to, references_json, message_id_header, in_reply_to, header_hash, cached_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "personal:[Gmail]/전체보관함:201",
                "personal",
                "[Gmail]/전체보관함",
                "201",
                '["you@example.com"]',
                '["boss@example.com"]',
                '["reply@example.com"]',
                "you@example.com",
                '["<a@example.com>"]',
                "<msg-201@example.com>",
                "<msg-200@example.com>",
                "hash-1",
                "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.commit()

    cached = _get_cached_message_participants(config.database_path, {"message_id": "personal:[Gmail]/전체보관함:201"})
    assert cached is not None
    assert cached["to"] == ["you@example.com"]
    assert cached["cc"] == ["boss@example.com"]
    assert cached["reply_to"] == ["reply@example.com"]
    assert cached["references"] == ["<a@example.com>"]
    assert cached["message_id"] == "<msg-201@example.com>"
    assert cached["in_reply_to"] == "<msg-200@example.com>"


def test_backfill_message_participant_cache_stores_exported_headers(tmp_path: Path):
    from jinwang_jarvis.bootstrap import bootstrap_workspace
    from jinwang_jarvis.config import load_pipeline_config
    import sqlite3

    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)
    rows = [{
        "message_id": "personal:[Gmail]/전체보관함:201",
        "account": "personal",
        "folder_name": "[Gmail]/전체보관함",
        "source_id": "201",
        "to_addr": "you@example.com",
    }]

    def exporter(row):
        return b"Message-ID: <msg-201@example.com>\nIn-Reply-To: <msg-200@example.com>\nTo: you@example.com\nCc: boss@example.com\nReply-To: reply@example.com\nDelivered-To: you@example.com\nReferences: <a@example.com>\n\n"

    result = _backfill_message_participant_cache(config.database_path, rows, exporter=exporter, limit=10)
    assert result["cached_count"] == 1
    with sqlite3.connect(config.database_path) as conn:
        record = conn.execute("SELECT to_addrs_json, cc_addrs_json, reply_to_addrs_json, message_id_header, in_reply_to FROM message_participant_cache WHERE message_id = ?", ("personal:[Gmail]/전체보관함:201",)).fetchone()
    assert record is not None
    assert json.loads(record[0]) == ["you@example.com"]
    assert json.loads(record[1]) == ["boss@example.com"]
    assert json.loads(record[2]) == ["reply@example.com"]
    assert record[3] == "<msg-201@example.com>"
    assert record[4] == "<msg-200@example.com>"


def test_systematic_backfill_message_participant_cache_queries_uncached_rows(tmp_path: Path):
    from jinwang_jarvis.bootstrap import bootstrap_workspace
    from jinwang_jarvis.config import load_pipeline_config
    import sqlite3

    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_messages (
                knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr, to_addrs_json, cc_addrs_json,
                self_role, interaction_role, sent_at, has_attachment, category, tags_json, importance_score,
                opportunity_score, summary_text, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "k1", "personal", "[Gmail]/전체보관함", "501", "Need review", "boss@example.com", "you@example.com",
                '["you@example.com"]', '[]', 'direct-to-me', 'review-request',
                "2026-04-19T10:00:00+00:00", 0, "technology", "[]", 0.9, 0.1,
                "summary", "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_messages (
                knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr, to_addrs_json, cc_addrs_json,
                self_role, interaction_role, sent_at, has_attachment, category, tags_json, importance_score,
                opportunity_score, summary_text, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "k2", "personal", "[Gmail]/전체보관함", "502", "Need update", "boss@example.com", "you@example.com",
                '["you@example.com"]', '[]', 'direct-to-me', 'direct-ask',
                "2026-04-18T10:00:00+00:00", 0, "technology", "[]", 0.8, 0.1,
                "summary", "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO message_participant_cache (message_id, account, folder_name, source_id, to_addrs_json, cc_addrs_json, reply_to_addrs_json, delivered_to, references_json, message_id_header, in_reply_to, header_hash, cached_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "k1", "personal", "[Gmail]/전체보관함", "501", '["you@example.com"]', '[]', '[]', 'you@example.com', '[]', '<k1>', None, 'h1', '2026-04-20T00:00:00+00:00'
            ),
        )
        conn.commit()

    def exporter(row):
        return f"Message-ID: <{row['source_id']}@example.com>\nTo: you@example.com\n\n".encode()

    result = _systematic_backfill_message_participant_cache(config.database_path, exporter=exporter, limit=10)
    assert result["candidate_count"] >= 1
    assert result["cached_count"] == 1


def test_infer_interaction_chains_marks_waiting_states_and_awareness():
    rows = [
        {"knowledge_id": "1", "subject": "Need budget update", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-10T10:00:00+00:00", "message_id_header": "<a1>", "in_reply_to": None, "references": []},
        {"knowledge_id": "2", "subject": "Re: Need budget update", "from_addr": "me@example.com", "to_addr": "boss@example.com", "self_role": "sent-by-me", "interaction_role": "status-reply", "sent_at": "2026-04-10T11:00:00+00:00", "message_id_header": "<a2>", "in_reply_to": "<a1>", "references": ["<a1>"]},
        {"knowledge_id": "3", "subject": "Need draft today", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-11T10:00:00+00:00", "message_id_header": "<b1>", "in_reply_to": None, "references": []},
        {"knowledge_id": "4", "subject": "Need old approval", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "decision-request", "sent_at": "2024-01-01T10:00:00+00:00", "message_id_header": "<c1>", "in_reply_to": None, "references": []},
        {"knowledge_id": "5", "subject": "Fwd: summit invite", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "fyi-forward", "sent_at": "2026-04-11T12:00:00+00:00", "message_id_header": "<d1>", "in_reply_to": None, "references": []},
    ]
    chains = _infer_interaction_chains(rows)
    by_subject = {item["latest_subject"]: item for item in chains}
    assert by_subject["Re: Need budget update"]["state"] == "waiting-on-others"
    assert by_subject["Need draft today"]["state"] == "waiting-on-me"
    assert by_subject["Need old approval"]["state"] == "stale-open"
    assert by_subject["Fwd: summit invite"]["state"] == "awareness-only"


def test_classify_jongwon_context_distinguishes_sender_recipient_and_cc_cases():
    self_addresses = {"jinwang@smartx.kr", "jinwangmok@gmail.com"}

    professor_sent = _classify_jongwon_context(
        {"from_addr": "jongwon@smartx.kr", "subject": "Re: 검토 요청", "to_addr": "jinwang@smartx.kr"},
        {"to": ["jinwang@smartx.kr"], "cc": [], "delivered_to": "jinwang@smartx.kr"},
        self_addresses,
    )
    assert professor_sent == "professor-sent-to-me-primary"

    professor_primary_me_cc = _classify_jongwon_context(
        {"from_addr": "member@smartx.kr", "subject": "보고드립니다", "to_addr": "jongwon@smartx.kr"},
        {"to": ["jongwon@smartx.kr"], "cc": ["jinwang@smartx.kr"], "delivered_to": "jinwang@smartx.kr"},
        self_addresses,
    )
    assert professor_primary_me_cc == "professor-primary-me-cc"

    professor_cced = _classify_jongwon_context(
        {"from_addr": "member@smartx.kr", "subject": "진행 상황 공유", "to_addr": "jinwang@smartx.kr"},
        {"to": ["jinwang@smartx.kr"], "cc": ["jongwon@smartx.kr"], "delivered_to": "jinwang@smartx.kr"},
        self_addresses,
    )
    assert professor_cced == "professor-cced"


def test_build_recent_action_alerts_includes_direct_mail_and_self_relay_forward_candidates():
    rows = [
        {
            "message_id": "m1",
            "account": "smartx",
            "subject": "[REMIND] [산자부E2E] GIST 서버 접근 안내 요청의 건",
            "from_addr": "seonmyeong.lee@kaist.ac.kr",
            "sent_at": "2026-04-16T11:25:00+00:00",
            "self_role": "direct-to-me",
            "interaction_role": "direct-ask",
            "is_seen": 1,
        },
        {
            "message_id": "m2",
            "account": "smartx",
            "subject": "FW: [2026 GIST AI융합학과 X AI정책전략대학원 체육대회] 경기 참가 및 관람여부 설문조사 응답 요청 (~4/24(금)까지)",
            "from_addr": "jinwangmok@gm.gist.ac.kr",
            "sent_at": "2026-04-20T11:21:00+00:00",
            "self_role": "sent-by-me",
            "interaction_role": "fyi-forward",
            "is_seen": 0,
        },
        {
            "message_id": "m3",
            "account": "smartx",
            "subject": "FW: (인재양성대전 2026) 부스 담당학생 대상 단톡방 개설 링크",
            "from_addr": "jinwangmok@gm.gist.ac.kr",
            "sent_at": "2026-04-21T02:14:00+00:00",
            "self_role": "sent-by-me",
            "interaction_role": "fyi-forward",
            "is_seen": 0,
        },
        {
            "message_id": "m4",
            "account": "personal",
            "subject": "일반 뉴스레터",
            "from_addr": "news@example.com",
            "sent_at": "2026-04-21T01:00:00+00:00",
            "self_role": "direct-to-me",
            "interaction_role": "other",
            "is_seen": 0,
        },
    ]

    alerts = _build_recent_action_alerts(rows)
    subjects = [item["subject"] for item in alerts]
    assert "[REMIND] [산자부E2E] GIST 서버 접근 안내 요청의 건" in subjects
    assert "FW: [2026 GIST AI융합학과 X AI정책전략대학원 체육대회] 경기 참가 및 관람여부 설문조사 응답 요청 (~4/24(금)까지)" in subjects
    assert "FW: (인재양성대전 2026) 부스 담당학생 대상 단톡방 개설 링크" in subjects
    assert "일반 뉴스레터" not in subjects

    by_subject = {item["subject"]: item for item in alerts}
    assert by_subject["[REMIND] [산자부E2E] GIST 서버 접근 안내 요청의 건"]["alert_type"] == "direct-action"
    assert by_subject["FW: [2026 GIST AI융합학과 X AI정책전략대학원 체육대회] 경기 참가 및 관람여부 설문조사 응답 요청 (~4/24(금)까지)"]["alert_type"] == "self-relay-action"
    assert by_subject["FW: (인재양성대전 2026) 부스 담당학생 대상 단톡방 개설 링크"]["alert_type"] == "self-relay-action"


def test_build_education_memory_records_promotes_career_like_items_and_filters_generic_notices():
    rows = [
        {
            "knowledge_id": "edu-1",
            "subject": "2026년도 교원연수 강사료 관련 서류 작성 요청",
            "from_addr": "gaeun218@gist.ac.kr",
            "self_role": "other",
            "interaction_role": "direct-ask",
            "sent_at": "2026-02-10T11:53:00+09:00",
        },
        {
            "knowledge_id": "edu-2",
            "subject": "고등학교 음악 교과서.zip",
            "from_addr": "editor@example.com",
            "self_role": "other",
            "interaction_role": "other",
            "sent_at": "2024-11-19T09:00:00+09:00",
        },
        {
            "knowledge_id": "edu-3",
            "subject": "4차산업혁명 트렌드분석 11월 5일 강의 자료공유 및 사전질문 요청",
            "from_addr": "host@example.com",
            "self_role": "other",
            "interaction_role": "direct-ask",
            "sent_at": "2024-10-28T09:00:00+09:00",
        },
        {
            "knowledge_id": "edu-4",
            "subject": "[학술정보팀] 2026 봄학기 도서관 이용자 교육(3월~4월)",
            "from_addr": "library@example.com",
            "self_role": "direct-to-me",
            "interaction_role": "other",
            "sent_at": "2026-03-12T17:05:00+09:00",
        },
        {
            "knowledge_id": "edu-5",
            "subject": "[상담센터] 2025년 정신건강특강(\"잠은 타협의 대상이 아니다\") 실시 안내",
            "from_addr": "notice@example.com",
            "self_role": "direct-to-me",
            "interaction_role": "other",
            "sent_at": "2025-11-21T17:18:00+09:00",
        },
    ]

    records = _build_education_memory_records(rows)

    titles = [record["event_name"] for record in records]
    assert "2026년도 교원연수 강사료 관련 서류 작성 요청" in titles
    assert "고등학교 음악 교과서" in titles
    assert "4차산업혁명 트렌드분석 11월 5일 강의 자료공유 및 사전질문 요청" in titles
    assert "[학술정보팀] 2026 봄학기 도서관 이용자 교육(3월~4월)" not in titles
    assert "[상담센터] 2025년 정신건강특강(\"잠은 타협의 대상이 아니다\") 실시 안내" not in titles

    by_title = {record["event_name"]: record for record in records}
    assert by_title["2026년도 교원연수 강사료 관련 서류 작성 요청"]["audience"] == "teachers"
    assert by_title["2026년도 교원연수 강사료 관련 서류 작성 요청"]["role"] == "instruction-support"
    assert by_title["고등학교 음악 교과서"]["audience"] == "high-school"
    assert by_title["고등학교 음악 교과서"]["role"] == "textbook-development"
    assert by_title["4차산업혁명 트렌드분석 11월 5일 강의 자료공유 및 사전질문 요청"]["role"] == "teaching-delivery"


def test_build_education_cv_sections_groups_records_for_cv_style_note():
    records = [
        {
            "event_name": "4차산업혁명 트렌드분석 11월 5일 강의 자료공유 및 사전질문 요청",
            "sent_at": "2024-10-28T09:00:00+09:00",
            "audience": "workers",
            "role": "teaching-delivery",
            "summary": "강의/교안/콘텐츠 전달 준비 흐름",
            "subject": "4차산업혁명 트렌드분석 11월 5일 강의 자료공유 및 사전질문 요청",
        },
        {
            "event_name": "고등학교 음악 교과서",
            "sent_at": "2024-11-19T09:00:00+09:00",
            "audience": "high-school",
            "role": "textbook-development",
            "summary": "교과서/교육자료 개발 또는 검토 흐름",
            "subject": "고등학교 음악 교과서.zip",
        },
        {
            "event_name": "2026년도 교원연수 강사료 관련 서류 작성 요청",
            "sent_at": "2026-02-10T11:53:00+09:00",
            "audience": "teachers",
            "role": "instruction-support",
            "summary": "교원연수 운영·정산·보고 관련 흐름",
            "subject": "2026년도 교원연수 강사료 관련 서류 작성 요청",
        },
    ]

    sections = _build_education_cv_sections(records)

    assert sections["teaching-delivery"][0]["event_name"].startswith("4차산업혁명")
    assert sections["textbook-development"][0]["event_name"] == "고등학교 음악 교과서"
    assert sections["instruction-support"][0]["audience"] == "teachers"
    assert sections["timeline"][0]["sent_at"] == "2026-02-10T11:53:00+09:00"


def test_collect_knowledge_mail_and_generate_daily_intelligence(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    runner = FakeKnowledgeRunner()

    collect_result = collect_knowledge_mail(config, months=36, runner=runner)
    assert collect_result["message_count"] == 4
    assert collect_result["accounts"][0]["all_mail_folder"] == "[Gmail]/전체보관함"

    report_result = generate_daily_intelligence_report(config, lookback_days=7)
    assert report_result["item_count"] == 2
    assert report_result["opportunity_count"] >= 1
    assert report_result["artifact_path"].exists()
    assert report_result["wiki_note_path"].exists()
    assert report_result["index_path"].exists()

    import sqlite3
    with sqlite3.connect(config.database_path) as conn:
        row = conn.execute("SELECT to_addrs_json, cc_addrs_json, self_role, interaction_role FROM knowledge_messages WHERE knowledge_id = ?", ("personal:[Gmail]/전체보관함:201",)).fetchone()
    assert row is not None
    assert json.loads(row[0]) == ["you@example.com"]
    assert json.loads(row[1]) == []
    assert row[2] == "other"
    assert row[3] == "broadcast" or row[3] == "other" or row[3] == "direct-ask"

    text = report_result["artifact_path"].read_text(encoding="utf-8")
    assert "Opportunity signals" in text
    assert "AI agent meetup registration open" in text
    assert "Global market update: oil and inflation" in text
    assert "HERMES TEST GIST-FORWARD STATIC-001" not in text
    assert "Random low-signal general note" not in text

    checkpoints = json.loads((tmp_path / "state" / "checkpoints.json").read_text(encoding="utf-8"))
    assert checkpoints["knowledge_mail"]["personal"]["message_count"] == 4
    assert checkpoints["daily_intelligence"]["latest"]["item_count"] == 2


def test_generate_daily_intelligence_promotes_jongwon_and_smartx_flow_notes(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    runner = FakeKnowledgeRunner()
    collect_knowledge_mail(config, months=36, runner=runner)

    import sqlite3

    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_messages (
                knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr,
                sent_at, has_attachment, category, tags_json, importance_score,
                opportunity_score, summary_text, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "jongwon-1",
                "personal",
                "[Gmail]/전체보관함",
                "301",
                "Re: 데이터 파이프라인 검토 요청",
                "jongwon@smartx.kr",
                "you@example.com",
                "2026-04-18T10:00:00+00:00",
                0,
                "technology",
                "[]",
                0.91,
                0.18,
                "[technology] Re: 데이터 파이프라인 검토 요청",
                "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_messages (
                knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr,
                sent_at, has_attachment, category, tags_json, importance_score,
                opportunity_score, summary_text, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "smartx-1",
                "personal",
                "[Gmail]/전체보관함",
                "302",
                "[NetCS Announce] [SmartX Info] DGX Spark 관련 이슈 troubleshooting",
                "ho.kim@smartx.kr",
                "you@example.com",
                "2026-04-17T10:00:00+00:00",
                0,
                "technology",
                "[]",
                0.89,
                0.12,
                "[technology] [NetCS Announce] [SmartX Info] DGX Spark 관련 이슈 troubleshooting",
                "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.commit()

    report_result = generate_daily_intelligence_report(config, lookback_days=7)

    index_text = report_result["index_path"].read_text(encoding="utf-8")
    assert "Priority flows" in index_text
    assert "jongwon-smartx-flow" in index_text

    flow_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-smartx-flow.md"
    assert flow_note.exists()
    flow_text = flow_note.read_text(encoding="utf-8")
    assert "jongwon@smartx.kr" in flow_text
    assert "[SmartX Info] DGX Spark 관련 이슈 troubleshooting" in flow_text
    assert "데이터 파이프라인 검토 요청" in flow_text
    assert "## Monthly direct vs shared flow" in flow_text
    assert "2026-04: direct=" in flow_text
    assert "## Monthly flow hotspots" in flow_text


def test_generate_daily_intelligence_creates_dedicated_jongwon_smartx_lane_notes(tmp_path: Path):
    config = load_pipeline_config(_write_config(tmp_path))
    runner = FakeKnowledgeRunner()
    collect_knowledge_mail(config, months=36, runner=runner)

    import sqlite3

    with sqlite3.connect(config.database_path) as conn:
        rows = [
            (
                "jongwon-action-1", "personal", "[Gmail]/전체보관함", "401",
                "Re: 데이터 파이프라인 검토 요청", "jongwon@smartx.kr", "you@example.com",
                '["you@example.com"]', '[]', 'direct-to-me', 'review-request',
                "2026-04-18T10:00:00+00:00", 0, "technology", "[]", 0.91, 0.18,
                "[technology] Re: 데이터 파이프라인 검토 요청", "2026-04-20T00:00:00+00:00",
            ),
            (
                "jongwon-action-2", "personal", "[Gmail]/전체보관함", "402",
                "Fwd: MCP Dev Summit Lands in Seoul this August", "jongwon@smartx.kr", "you@example.com",
                '["you@example.com"]', '[]', 'direct-to-me', 'fyi-forward',
                "2026-04-17T10:00:00+00:00", 0, "opportunity", "[]", 0.85, 0.55,
                "[opportunity] Fwd: MCP Dev Summit Lands in Seoul this August", "2026-04-20T00:00:00+00:00",
            ),
            (
                "smartx-weekly-1", "personal", "[Gmail]/전체보관함", "403",
                "[NetCS Announce] [SmartX Info] DGX Spark 관련 이슈 troubleshooting", "ho.kim@smartx.kr", "you@example.com",
                '["you@example.com"]', '[]', 'other', 'broadcast',
                "2026-04-17T09:00:00+00:00", 0, "technology", "[]", 0.88, 0.12,
                "[technology] [NetCS Announce] [SmartX Info] DGX Spark 관련 이슈 troubleshooting", "2026-04-20T00:00:00+00:00",
            ),
            (
                "smartx-weekly-2", "personal", "[Gmail]/전체보관함", "404",
                "[NetCS Announce] [SmartX Info] [정보보안팀] React 취약점 공격 IP 차단조치", "brave@gist.ac.kr", "you@example.com",
                '["you@example.com"]', '[]', 'other', 'broadcast',
                "2026-04-16T09:00:00+00:00", 0, "technology", "[]", 0.87, 0.10,
                "[technology] [NetCS Announce] [SmartX Info] [정보보안팀] React 취약점 공격 IP 차단조치", "2026-04-20T00:00:00+00:00",
            ),
            (
                "edu-1", "personal", "[Gmail]/전체보관함", "405",
                "Dream AI 교원연수 운영 일정표 공유 및 준비 관련 안내", "iamtina@gist.ac.kr", "you@example.com",
                '["you@example.com"]', '[]', 'direct-to-me', 'direct-ask',
                "2026-01-10T10:00:00+00:00", 0, "technology", "[]", 0.83, 0.05,
                "[technology] Dream AI 교원연수 운영 일정표 공유 및 준비 관련 안내", "2026-04-20T00:00:00+00:00",
            ),
            (
                "edu-2", "personal", "[Gmail]/전체보관함", "406",
                "2026년도 교원연수 강사료 관련 서류 작성 요청", "gaeun218@gist.ac.kr", "you@example.com",
                '["you@example.com"]', '[]', 'direct-to-me', 'direct-ask',
                "2026-02-05T10:00:00+00:00", 0, "admin", "[]", 0.78, 0.0,
                "[admin] 2026년도 교원연수 강사료 관련 서류 작성 요청", "2026-04-20T00:00:00+00:00",
            ),
            (
                "edu-3", "personal", "[Gmail]/전체보관함", "407",
                "광주 인공지능 교과서 및 Star-MOOC 관련 인턴 지원 요청드립니다.", "cyk95780@gist.ac.kr", "you@example.com",
                '["you@example.com"]', '[]', 'direct-to-me', 'direct-ask',
                "2025-01-10T10:00:00+00:00", 0, "opportunity", "[]", 0.82, 0.2,
                "[opportunity] 광주 인공지능 교과서 및 Star-MOOC 관련 인턴 지원 요청드립니다.", "2026-04-20T00:00:00+00:00",
            ),
        ]
        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_messages (
                    knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr, to_addrs_json, cc_addrs_json,
                    self_role, interaction_role, sent_at, has_attachment, category, tags_json, importance_score,
                    opportunity_score, summary_text, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        message_rows = [
            (
                "smartx:INBOX:1", "smartx", "inbox", None,
                "[REMIND] [산자부E2E] (카이스트) GIST 서버 접근 안내 요청의 건", "seonmyeong.lee@kaist.ac.kr", '["jinwang@smartx.kr"]', '[]',
                "2026-04-20T08:25:00+09:00", None, None, None, 1, "2026-04-20T00:00:00+00:00", "direct-to-me", "direct-ask",
            ),
            (
                "smartx:INBOX:2", "smartx", "inbox", None,
                "FW: [2026 GIST AI융합학과 X AI정책전략대학원 체육대회] 경기 참가 및 관람여부 설문조사 응답 요청 (~4/24(금)까지)", "jinwangmok@gm.gist.ac.kr", '["jinwang@smartx.kr"]', '[]',
                "2026-04-20T18:21:00+09:00", None, None, None, 0, "2026-04-20T00:00:00+00:00", "sent-by-me", "fyi-forward",
            ),
            (
                "smartx:INBOX:hist1", "smartx", "inbox", None,
                "[산자부E2E] (카이스트) GIST 서버 접근 안내 요청의 건", "seonmyeong.lee@kaist.ac.kr", '["jinwang@smartx.kr"]', '[]',
                "2026-03-10T09:00:00+09:00", None, None, None, 1, "2026-03-10T00:00:00+00:00", "direct-to-me", "direct-ask",
            ),
            (
                "smartx:SENT:hist1-reply", "smartx", "sent", None,
                "Re: [산자부E2E] (카이스트) GIST 서버 접근 안내 요청의 건", "jinwang@smartx.kr", '["seonmyeong.lee@kaist.ac.kr"]', '[]',
                "2026-03-10T15:30:00+09:00", None, None, None, 1, "2026-03-10T00:00:00+00:00", "sent-by-me", "status-reply",
            ),
            (
                "smartx:INBOX:hist2", "smartx", "inbox", None,
                "FW: [2025 GIST AI융합학과 X AI정책전략대학원 체육대회] 경기 참가 및 관람여부 설문조사 응답 요청", "jinwangmok@gm.gist.ac.kr", '["jinwang@smartx.kr"]', '[]',
                "2026-03-20T11:00:00+09:00", None, None, None, 1, "2026-03-20T00:00:00+00:00", "sent-by-me", "fyi-forward",
            ),
        ]
        for row in message_rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO messages (
                    message_id, account, folder_kind, thread_key, subject, from_addr, to_addrs, cc_addrs,
                    sent_at, snippet, body_path, raw_json_path, is_seen, ingested_at, self_role, interaction_role
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO calendar_events (
                event_id, calendar_id, summary, status, start_ts, end_ts, location, html_link, dedup_key, raw_json_path, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evt-1", "primary", "Existing meeting", "confirmed",
                "2026-04-21T10:00:00+09:00", "2026-04-21T11:00:00+09:00", None, None, "existing-meeting-20260421-1000", None, "2026-04-20T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO event_proposals (
                proposal_id, source_message_id, title, start_ts, end_ts, location, description_md, confidence, status, dedup_key, reason_json, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "proposal-1", "smartx:INBOX:2", "체육대회 응답 관련 일정",
                "2026-04-21T15:00:00+09:00", "2026-04-21T16:00:00+09:00", None, None, 0.88, "proposed", "sports-day-reply-20260421-1500", "{}", "2026-04-20T00:00:00+00:00", None,
            ),
        )
        conn.commit()

    report_result = generate_daily_intelligence_report(
        config,
        lookback_days=7,
        as_of=datetime(2026, 4, 20, 10, 5, tzinfo=UTC),
    )

    index_text = report_result["index_path"].read_text(encoding="utf-8")
    assert "jongwon-direct-actions" in index_text
    assert "smartx-weekly-briefing" in index_text
    assert "jongwon-phase-map" in index_text
    assert "jongwon-context-cases" in index_text
    assert "interaction-chain-status" in index_text
    assert "advisor-action-status" in index_text
    assert "education-teaching-memory" in index_text
    assert "project-work-items" in index_text
    assert "recent-action-alerts" in index_text
    assert "next-day-mail-todos" in index_text
    assert "important-mail-recommendations" in index_text

    direct_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-direct-actions.md"
    weekly_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/smartx-weekly-briefing.md"
    phase_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-phase-map.md"
    context_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-context-cases.md"
    chain_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/interaction-chain-status.md"
    advisor_action_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/advisor-action-status.md"
    education_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/education-teaching-memory.md"
    project_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/project-work-items.md"
    recent_action_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/recent-action-alerts.md"
    next_day_todo_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/next-day-mail-todos.md"
    important_mail_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/important-mail-recommendations.md"
    assert direct_note.exists()
    assert weekly_note.exists()
    assert phase_note.exists()
    assert context_note.exists()
    assert chain_note.exists()
    assert advisor_action_note.exists()
    assert education_note.exists()
    assert project_note.exists()
    assert recent_action_note.exists()
    assert next_day_todo_note.exists()
    assert important_mail_note.exists()

    direct_text = direct_note.read_text(encoding="utf-8")
    assert "데이터 파이프라인 검토 요청" in direct_text
    assert "MCP Dev Summit" in direct_text
    assert "## Action-like mails" in direct_text

    weekly_text = weekly_note.read_text(encoding="utf-8")
    assert "DGX Spark 관련 이슈 troubleshooting" in weekly_text
    assert "React 취약점 공격 IP 차단조치" in weekly_text
    assert "## Security / ops watch" in weekly_text

    phase_text = phase_note.read_text(encoding="utf-8")
    assert "## Monthly phase map" in phase_text
    assert "2026-04" in phase_text

    context_text = context_note.read_text(encoding="utf-8")
    assert "## professor-sent-involving-me" in context_text

    chain_text = chain_note.read_text(encoding="utf-8")
    assert "## waiting-on-me" in chain_text
    assert "## waiting-on-others" in chain_text

    advisor_action_text = advisor_action_note.read_text(encoding="utf-8")
    assert "## do-now" in advisor_action_text
    assert "데이터 파이프라인 검토 요청" in advisor_action_text

    project_text = project_note.read_text(encoding="utf-8")
    assert "## Active work items" in project_text
    assert "data-platform" in project_text

    recent_action_text = recent_action_note.read_text(encoding="utf-8")
    assert "## Direct action mail" in recent_action_text
    assert "## Self-relay action candidates" in recent_action_text
    assert "설문조사 응답 요청" in recent_action_text

    next_day_todo_text = next_day_todo_note.read_text(encoding="utf-8")
    assert "# Next-day TODO from mail" in next_day_todo_text
    assert "Window (KST): 2026-04-19 19:00 ~ 2026-04-20 19:00" in next_day_todo_text
    assert "## Draft TODO for tomorrow" in next_day_todo_text
    assert "GIST 서버 접근 안내 요청의 건" in next_day_todo_text
    assert "설문조사 응답 요청" in next_day_todo_text

    important_mail_text = important_mail_note.read_text(encoding="utf-8")
    assert "# Important mail recommendations" in important_mail_text
    assert "message_id: smartx:INBOX:1" in important_mail_text
    assert "message_id: smartx:INBOX:2" in important_mail_text
    assert "replied_count: 1" in important_mail_text
    assert "median_response_hours: 6.5" in important_mail_text
    assert "메일에서 추출된 일정 후보 우선: 04-21 15:00~16:00" in important_mail_text
    assert "내일 캘린더 빈 시간 기준 추천:" in important_mail_text

    education_text = education_note.read_text(encoding="utf-8")
    assert "## Direct teaching / training" in education_text
    assert "## Textbook / material development" in education_text
    assert "## Education operations / support" in education_text
    assert "## Selected timeline" in education_text
    assert "date=2025-01-10" in education_text
    assert "audience=teachers" in education_text
    assert "role=textbook-development" in education_text
    assert "광주 인공지능 교과서 및 Star-MOOC 관련 인턴 지원 요청드립니다." in education_text
    assert "도서관 이용자 교육" not in education_text
    assert "정신건강특강" not in education_text
