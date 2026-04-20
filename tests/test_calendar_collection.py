import json
from pathlib import Path

from jinwang_jarvis.calendar import collect_calendar_snapshots
from jinwang_jarvis.config import load_pipeline_config


class FakeCalendarRunner:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        key = tuple(args)
        responses = {
            (
                "gws",
                "calendar",
                "events",
                "list",
                "--params",
                '{"calendarId":"primary","maxResults":5,"singleEvents":true,"orderBy":"startTime","timeMin":"2026-04-19T00:00:00+09:00","timeMax":"2026-05-19T00:00:00+09:00"}',
                "--format",
                "json",
            ): json.dumps(
                {
                    "items": [
                        {
                            "id": "evt-1",
                            "summary": "Advanced Computer Networking",
                            "status": "confirmed",
                            "start": {"dateTime": "2026-04-21T13:00:00+09:00", "timeZone": "Asia/Seoul"},
                            "end": {"dateTime": "2026-04-21T14:30:00+09:00", "timeZone": "Asia/Seoul"},
                        },
                        {
                            "id": "evt-2",
                            "summary": "[TA] SW 기초 및 코딩",
                            "status": "confirmed",
                            "start": {"dateTime": "2026-04-22T13:00:00+09:00", "timeZone": "Asia/Seoul"},
                            "end": {"dateTime": "2026-04-22T16:00:00+09:00", "timeZone": "Asia/Seoul"},
                        },
                    ]
                },
                ensure_ascii=False,
            )
        }
        try:
            return responses[key]
        except KeyError as exc:
            raise AssertionError(f"unexpected command: {args}") from exc


def test_collect_calendar_snapshots_writes_jsonl_and_updates_checkpoints(tmp_path: Path):
    config_file = tmp_path / "pipeline.yaml"
    config_file.write_text(
        """
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
    runner = FakeCalendarRunner()

    result = collect_calendar_snapshots(config, runner=runner.run)

    assert result["event_count"] == 2
    assert result["calendar_id"] == "primary"

    snapshot_files = list((tmp_path / "data" / "snapshots" / "calendar").glob("*.jsonl"))
    assert len(snapshot_files) == 1
    lines = snapshot_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert {row["summary"] for row in payloads} == {"Advanced Computer Networking", "[TA] SW 기초 및 코딩"}

    checkpoints = json.loads((tmp_path / "state" / "checkpoints.json").read_text(encoding="utf-8"))
    assert checkpoints["calendar"]["primary"]["last_snapshot_file"] == snapshot_files[0].name
    assert checkpoints["calendar"]["primary"]["event_count"] == 2
