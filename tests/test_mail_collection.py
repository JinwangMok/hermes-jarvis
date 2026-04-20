import json
from pathlib import Path

from jinwang_jarvis.config import load_pipeline_config
from jinwang_jarvis.mail import collect_mail_snapshots


class FakeCommandRunner:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        key = tuple(args)
        responses = {
            (
                "himalaya",
                "folder",
                "list",
                "-a",
                "personal",
            ): "| NAME | DESC |\n|------|------|\n| INBOX | \\HasNoChildren |\n| [Gmail]/보낸편지함 | \\HasNoChildren, \\Sent |\n",
            (
                "himalaya",
                "envelope",
                "list",
                "-a",
                "personal",
                "--page-size",
                "2",
                "--output",
                "json",
            ): '[{"id":"10","flags":[],"subject":"Inbox test","from":{"name":"Google","addr":"no-reply@accounts.google.com"},"to":{"name":null,"addr":"jinwangmok@gmail.com"},"date":"2026-04-19 14:16+00:00","has_attachment":false}]',
            (
                "himalaya",
                "envelope",
                "list",
                "-a",
                "personal",
                "--folder",
                "[Gmail]/보낸편지함",
                "--page-size",
                "2",
                "--output",
                "json",
            ): '[{"id":"11","flags":["Seen"],"subject":"Sent test","from":{"name":null,"addr":"jinwangmok@gmail.com"},"to":{"name":null,"addr":"jinwangmok@gm.gist.ac.kr"},"date":"2026-04-19 14:17+00:00","has_attachment":false}]',
        }
        try:
            return responses[key]
        except KeyError as exc:
            raise AssertionError(f"unexpected command: {args}") from exc


def test_collect_mail_snapshots_writes_jsonl_and_updates_checkpoints(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(
        """
workspace_root: {root}
wiki_root: /home/jinwang/wiki
accounts:
  - personal
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 2
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
""".format(root=tmp_path.as_posix()),
        encoding="utf-8",
    )
    config = load_pipeline_config(config_file)
    runner = FakeCommandRunner()

    result = collect_mail_snapshots(config, runner=runner.run)

    assert result["accounts"][0]["account"] == "personal"
    assert result["accounts"][0]["inbox_count"] == 1
    assert result["accounts"][0]["sent_count"] == 1
    assert result["accounts"][0]["sent_folder"] == "[Gmail]/보낸편지함"

    snapshot_files = list((tmp_path / "data" / "snapshots" / "mail").glob("*.jsonl"))
    assert len(snapshot_files) == 1
    lines = snapshot_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert {row["folder_kind"] for row in payloads} == {"inbox", "sent"}

    checkpoints = json.loads((tmp_path / "state" / "checkpoints.json").read_text(encoding="utf-8"))
    assert checkpoints["mail"]["personal"]["last_snapshot_file"] == snapshot_files[0].name
    assert checkpoints["mail"]["personal"]["sent_folder"] == "[Gmail]/보낸편지함"
