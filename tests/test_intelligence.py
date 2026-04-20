import json
from pathlib import Path

from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.intelligence import (
    _backfill_message_participant_cache,
    _classify_jongwon_context,
    _get_cached_message_participants,
    _infer_interaction_chains,
    _parse_participant_headers,
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
        {"knowledge_id": "1", "subject": "Please review architecture", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "review-request", "sent_at": "2026-04-10T10:00:00+00:00"},
        {"knowledge_id": "2", "subject": "Re: Please review architecture", "from_addr": "me@example.com", "to_addr": "boss@example.com", "self_role": "sent-by-me", "interaction_role": "status-reply", "sent_at": "2026-04-10T12:00:00+00:00"},
        {"knowledge_id": "3", "subject": "Need update on budget", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-11T10:00:00+00:00"},
        {"knowledge_id": "4", "subject": "Re: Need update on budget", "from_addr": "me@example.com", "to_addr": "boss@example.com", "self_role": "sent-by-me", "interaction_role": "status-reply", "sent_at": "2026-04-11T11:00:00+00:00"},
        {"knowledge_id": "5", "subject": "Re: Need update on budget", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-11T12:00:00+00:00"},
        {"knowledge_id": "6", "subject": "Submit draft today", "from_addr": "boss@example.com", "to_addr": "me@example.com", "self_role": "direct-to-me", "interaction_role": "direct-ask", "sent_at": "2026-04-12T10:00:00+00:00"},
        {"knowledge_id": "7", "subject": "[SmartX Info] infra weekly", "from_addr": "info@smartx.kr", "to_addr": "info@smartx.kr", "self_role": "other", "interaction_role": "broadcast", "sent_at": "2026-04-12T09:00:00+00:00"},
    ]
    chains = _infer_interaction_chains(rows)
    by_subject = {item["subject_key"]: item for item in chains}
    assert by_subject["please review architecture"]["state"] == "replied"
    assert by_subject["need update on budget"]["state"] == "follow-up-pending"
    assert by_subject["submit draft today"]["state"] == "pending"
    assert "smartx info infra weekly" not in by_subject


def test_parse_participant_headers_extracts_to_cc_reply_to_and_references():
    raw = b"""From: sender@example.com\nTo: me@example.com, team@example.com\nCc: boss@example.com\nReply-To: reply@example.com\nDelivered-To: me@example.com\nReferences: <a@example.com> <b@example.com>\nSubject: test\n\nbody\n"""
    parsed = _parse_participant_headers(raw)
    assert parsed["to"] == ["me@example.com", "team@example.com"]
    assert parsed["cc"] == ["boss@example.com"]
    assert parsed["reply_to"] == ["reply@example.com"]
    assert parsed["delivered_to"] == "me@example.com"
    assert parsed["references"] == ["<a@example.com>", "<b@example.com>"]


def test_cached_message_participants_roundtrip(tmp_path: Path):
    from jinwang_jarvis.bootstrap import bootstrap_workspace
    from jinwang_jarvis.config import load_pipeline_config
    import sqlite3

    config = load_pipeline_config(_write_config(tmp_path))
    bootstrap_workspace(config)
    with sqlite3.connect(config.database_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO message_participant_cache (message_id, account, folder_name, source_id, to_addrs_json, cc_addrs_json, reply_to_addrs_json, delivered_to, references_json, header_hash, cached_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        return b"To: you@example.com\nCc: boss@example.com\nReply-To: reply@example.com\nDelivered-To: you@example.com\nReferences: <a@example.com>\n\n"

    result = _backfill_message_participant_cache(config.database_path, rows, exporter=exporter, limit=10)
    assert result["cached_count"] == 1
    with sqlite3.connect(config.database_path) as conn:
        record = conn.execute("SELECT to_addrs_json, cc_addrs_json, reply_to_addrs_json FROM message_participant_cache WHERE message_id = ?", ("personal:[Gmail]/전체보관함:201",)).fetchone()
    assert record is not None
    assert json.loads(record[0]) == ["you@example.com"]
    assert json.loads(record[1]) == ["boss@example.com"]
    assert json.loads(record[2]) == ["reply@example.com"]


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
                "2026-04-18T10:00:00+00:00", 0, "technology", "[]", 0.91, 0.18,
                "[technology] Re: 데이터 파이프라인 검토 요청", "2026-04-20T00:00:00+00:00",
            ),
            (
                "jongwon-action-2", "personal", "[Gmail]/전체보관함", "402",
                "Fwd: MCP Dev Summit Lands in Seoul this August", "jongwon@smartx.kr", "you@example.com",
                "2026-04-17T10:00:00+00:00", 0, "opportunity", "[]", 0.85, 0.55,
                "[opportunity] Fwd: MCP Dev Summit Lands in Seoul this August", "2026-04-20T00:00:00+00:00",
            ),
            (
                "smartx-weekly-1", "personal", "[Gmail]/전체보관함", "403",
                "[NetCS Announce] [SmartX Info] DGX Spark 관련 이슈 troubleshooting", "ho.kim@smartx.kr", "you@example.com",
                "2026-04-17T09:00:00+00:00", 0, "technology", "[]", 0.88, 0.12,
                "[technology] [NetCS Announce] [SmartX Info] DGX Spark 관련 이슈 troubleshooting", "2026-04-20T00:00:00+00:00",
            ),
            (
                "smartx-weekly-2", "personal", "[Gmail]/전체보관함", "404",
                "[NetCS Announce] [SmartX Info] [정보보안팀] React 취약점 공격 IP 차단조치", "brave@gist.ac.kr", "you@example.com",
                "2026-04-16T09:00:00+00:00", 0, "technology", "[]", 0.87, 0.10,
                "[technology] [NetCS Announce] [SmartX Info] [정보보안팀] React 취약점 공격 IP 차단조치", "2026-04-20T00:00:00+00:00",
            ),
        ]
        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_messages (
                    knowledge_id, account, folder_name, source_id, subject, from_addr, to_addr,
                    sent_at, has_attachment, category, tags_json, importance_score,
                    opportunity_score, summary_text, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.commit()

    report_result = generate_daily_intelligence_report(config, lookback_days=7)

    index_text = report_result["index_path"].read_text(encoding="utf-8")
    assert "jongwon-direct-actions" in index_text
    assert "smartx-weekly-briefing" in index_text
    assert "jongwon-phase-map" in index_text
    assert "jongwon-context-cases" in index_text
    assert "interaction-chain-status" in index_text

    direct_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-direct-actions.md"
    weekly_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/smartx-weekly-briefing.md"
    phase_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-phase-map.md"
    context_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-context-cases.md"
    chain_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/interaction-chain-status.md"
    assert direct_note.exists()
    assert weekly_note.exists()
    assert phase_note.exists()
    assert context_note.exists()
    assert chain_note.exists()

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
    assert "## follow-up-pending" in chain_text
