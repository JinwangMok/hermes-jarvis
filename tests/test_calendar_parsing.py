import json

from jinwang_jarvis.calendar import build_dedup_key, normalize_calendar_event


def test_normalize_calendar_event_maps_gws_json_to_snapshot_record():
    event = {
        "id": "evt-123",
        "summary": "[TA] SW 기초 및 코딩",
        "status": "confirmed",
        "start": {"dateTime": "2026-04-22T13:00:00+09:00", "timeZone": "Asia/Seoul"},
        "end": {"dateTime": "2026-04-22T16:00:00+09:00", "timeZone": "Asia/Seoul"},
        "location": "Room 101",
        "htmlLink": "https://calendar.google.com/example",
    }

    record = normalize_calendar_event(calendar_id="primary", event=event)

    assert record["event_id"] == "evt-123"
    assert record["calendar_id"] == "primary"
    assert record["summary"] == "[TA] SW 기초 및 코딩"
    assert record["start_ts"] == "2026-04-22T13:00:00+09:00"
    assert record["end_ts"] == "2026-04-22T16:00:00+09:00"
    assert record["location"] == "Room 101"
    assert record["dedup_key"] == build_dedup_key("[TA] SW 기초 및 코딩", "2026-04-22T13:00:00+09:00")

    json.dumps(record, ensure_ascii=False)


def test_build_dedup_key_normalizes_summary_and_start_time():
    key = build_dedup_key("  [TA] SW 기초 및 코딩  ", "2026-04-22T13:00:00+09:00")

    assert key == "[ta] sw 기초 및 코딩|2026-04-22t13:00:00+09:00"
