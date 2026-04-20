import json
from pathlib import Path

from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.intelligence import collect_knowledge_mail, generate_daily_intelligence_report


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

    direct_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-direct-actions.md"
    weekly_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/smartx-weekly-briefing.md"
    phase_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-phase-map.md"
    assert direct_note.exists()
    assert weekly_note.exists()
    assert phase_note.exists()

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
