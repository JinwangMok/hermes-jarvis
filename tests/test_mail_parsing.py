import json
from pathlib import Path

from jinwang_jarvis.mail import (
    FolderInfo,
    choose_sent_folder,
    normalize_envelope,
    parse_folder_list_table,
)


def test_parse_folder_list_table_extracts_folder_names_and_flags():
    output = """| NAME               | DESC                     |
|--------------------|--------------------------|
| INBOX              | \\HasNoChildren           |
| [Gmail]/보낸편지함 | \\HasNoChildren, \\Sent   |
| Sent               | \\HasNoChildren           |
"""

    folders = parse_folder_list_table(output)

    assert folders == [
        FolderInfo(name="INBOX", flags=("\\HasNoChildren",)),
        FolderInfo(name="[Gmail]/보낸편지함", flags=("\\HasNoChildren", "\\Sent")),
        FolderInfo(name="Sent", flags=("\\HasNoChildren",)),
    ]


def test_choose_sent_folder_prefers_sent_flag_then_common_names():
    folders = [
        FolderInfo(name="INBOX", flags=("\\HasNoChildren",)),
        FolderInfo(name="Sent", flags=("\\HasNoChildren",)),
        FolderInfo(name="[Gmail]/보낸편지함", flags=("\\HasNoChildren", "\\Sent")),
    ]

    assert choose_sent_folder("personal", folders, overrides={}) == "[Gmail]/보낸편지함"
    assert choose_sent_folder("personal", [FolderInfo(name="Sent", flags=("\\HasNoChildren",))], overrides={}) == "Sent"


def test_normalize_envelope_maps_himalaya_json_to_snapshot_record():
    envelope = {
        "id": "2561",
        "flags": [],
        "subject": "FW: Security alert for jinwangmok@gmail.com",
        "from": {"name": "목진왕", "addr": "jinwangmok@gm.gist.ac.kr"},
        "to": {"name": "jinwang@smartx.kr", "addr": "jinwang@smartx.kr"},
        "date": "2026-04-19 14:16+00:00",
        "has_attachment": False,
    }

    record = normalize_envelope(account="smartx", folder_kind="inbox", folder_name="INBOX", envelope=envelope)

    assert record["message_id"] == "smartx:INBOX:2561"
    assert record["source_id"] == "2561"
    assert record["account"] == "smartx"
    assert record["folder_kind"] == "inbox"
    assert record["folder_name"] == "INBOX"
    assert record["subject"] == "FW: Security alert for jinwangmok@gmail.com"
    assert record["from_addr"] == "jinwangmok@gm.gist.ac.kr"
    assert record["to_addr"] == "jinwang@smartx.kr"
    assert record["flags"] == []
    assert record["has_attachment"] is False

    json.dumps(record, ensure_ascii=False)
