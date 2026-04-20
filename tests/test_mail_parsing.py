import json
from pathlib import Path

from jinwang_jarvis.mail import (
    FolderInfo,
    _derive_interaction_role,
    _derive_self_role,
    _extract_addresses,
    choose_all_mail_folder,
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


def test_choose_all_mail_folder_prefers_all_flag_then_common_names():
    folders = [
        FolderInfo(name="INBOX", flags=("\\HasNoChildren",)),
        FolderInfo(name="Archive", flags=("\\HasNoChildren",)),
        FolderInfo(name="[Gmail]/전체보관함", flags=("\\HasNoChildren", "\\All")),
    ]

    assert choose_all_mail_folder("personal", folders) == "[Gmail]/전체보관함"
    assert choose_all_mail_folder("personal", [FolderInfo(name="Archive", flags=("\\HasNoChildren",))]) == "Archive"


def test_extract_addresses_supports_dict_and_list_values():
    assert _extract_addresses({"name": "A", "addr": "a@example.com"}) == ["a@example.com"]
    assert _extract_addresses([
        {"name": "A", "addr": "a@example.com"},
        {"name": "B", "addr": "b@example.com"},
    ]) == ["a@example.com", "b@example.com"]


def test_derive_roles_distinguishes_sent_direct_cc_and_broadcast():
    self_addresses = {"me@example.com"}
    assert _derive_self_role(folder_kind="sent", from_addr="me@example.com", to_addrs=["you@example.com"], cc_addrs=[], self_addresses=self_addresses) == "sent-by-me"
    assert _derive_self_role(folder_kind="inbox", from_addr="boss@example.com", to_addrs=["me@example.com"], cc_addrs=[], self_addresses=self_addresses) == "direct-to-me"
    assert _derive_self_role(folder_kind="inbox", from_addr="boss@example.com", to_addrs=["team@example.com"], cc_addrs=["me@example.com"], self_addresses=self_addresses) == "cc-me"
    assert _derive_interaction_role(folder_kind="inbox", subject="Please review draft", from_addr="boss@example.com", to_addrs=["me@example.com"], cc_addrs=[], self_addresses=self_addresses) == "review-request"
    assert _derive_interaction_role(folder_kind="sent", subject="Status report 제출", from_addr="me@example.com", to_addrs=["boss@example.com"], cc_addrs=[], self_addresses=self_addresses) == "status-reply"
    assert _derive_interaction_role(folder_kind="inbox", subject="Fwd: MCP summit", from_addr="boss@example.com", to_addrs=["me@example.com"], cc_addrs=[], self_addresses=self_addresses) == "fyi-forward"
    assert _derive_interaction_role(folder_kind="inbox", subject="[SmartX Info] Weekly infra update", from_addr="info@smartx.kr", to_addrs=["info@smartx.kr"], cc_addrs=[], self_addresses=self_addresses) == "broadcast"


def test_normalize_envelope_maps_himalaya_json_to_snapshot_record():
    envelope = {
        "id": "2561",
        "flags": [],
        "subject": "FW: Security alert for jinwangmok@gmail.com",
        "from": {"name": "목진왕", "addr": "jinwangmok@gm.gist.ac.kr"},
        "to": [
            {"name": "jinwang@smartx.kr", "addr": "jinwang@smartx.kr"},
            {"name": "lab@smartx.kr", "addr": "lab@smartx.kr"},
        ],
        "cc": [
            {"name": "jongwon@smartx.kr", "addr": "jongwon@smartx.kr"},
        ],
        "date": "2026-04-19 14:16+00:00",
        "has_attachment": False,
    }

    record = normalize_envelope(
        account="smartx",
        folder_kind="inbox",
        folder_name="INBOX",
        envelope=envelope,
        self_addresses={"jinwang@smartx.kr"},
    )

    assert record["message_id"] == "smartx:INBOX:2561"
    assert record["source_id"] == "2561"
    assert record["account"] == "smartx"
    assert record["folder_kind"] == "inbox"
    assert record["folder_name"] == "INBOX"
    assert record["subject"] == "FW: Security alert for jinwangmok@gmail.com"
    assert record["from_addr"] == "jinwangmok@gm.gist.ac.kr"
    assert record["to_addr"] == "jinwang@smartx.kr"
    assert record["to_addrs"] == ["jinwang@smartx.kr", "lab@smartx.kr"]
    assert record["cc_addrs"] == ["jongwon@smartx.kr"]
    assert record["self_role"] == "direct-to-me"
    assert record["interaction_role"] == "fyi-forward"
    assert record["flags"] == []
    assert record["has_attachment"] is False

    json.dumps(record, ensure_ascii=False)
