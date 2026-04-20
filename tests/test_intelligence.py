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
