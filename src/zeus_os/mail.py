from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig

COMMON_SENT_FOLDER_NAMES = (
    "sent",
    "sent mail",
    "[gmail]/보낸편지함",
    "[gmail]/sent mail",
)

COMMON_ALL_MAIL_FOLDER_NAMES = (
    "[gmail]/전체보관함",
    "[gmail]/all mail",
    "all mail",
    "archive",
)


@dataclass(frozen=True)
class FolderInfo:
    name: str
    flags: tuple[str, ...]


def parse_folder_list_table(output: str) -> list[FolderInfo]:
    folders: list[FolderInfo] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0].upper() == "NAME":
            continue
        if set(cells[0]) == {"-"}:
            continue
        flags = tuple(part.strip() for part in cells[1].split(",") if part.strip())
        folders.append(FolderInfo(name=cells[0], flags=flags))
    return folders


def choose_sent_folder(account: str, folders: Iterable[FolderInfo], overrides: dict[str, str]) -> str:
    if account in overrides:
        return overrides[account]

    folders = list(folders)
    for folder in folders:
        if "\\Sent" in folder.flags:
            return folder.name

    lowered = {folder.name.casefold(): folder.name for folder in folders}
    for candidate in COMMON_SENT_FOLDER_NAMES:
        if candidate in lowered:
            return lowered[candidate]

    raise ValueError(f"could not determine sent folder for account {account}")


def choose_all_mail_folder(account: str, folders: Iterable[FolderInfo]) -> str:
    folders = list(folders)
    for folder in folders:
        if "\\All" in folder.flags:
            return folder.name

    lowered = {folder.name.casefold(): folder.name for folder in folders}
    for candidate in COMMON_ALL_MAIL_FOLDER_NAMES:
        if candidate in lowered:
            return lowered[candidate]

    raise ValueError(f"could not determine all-mail folder for account {account}")


def _extract_addresses(value: dict | list[dict] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, dict):
        addr = (value.get("addr") or "").strip().lower()
        return [addr] if addr else []
    addresses: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        addr = (item.get("addr") or "").strip().lower()
        if addr and addr not in addresses:
            addresses.append(addr)
    return addresses


def _derive_self_role(*, folder_kind: str | None = None, from_addr: str | None, to_addrs: list[str], cc_addrs: list[str], self_addresses: set[str] | None) -> str:
    sender = (from_addr or "").strip().lower()
    self_set = {addr.strip().lower() for addr in (self_addresses or set()) if addr.strip()}
    if (folder_kind or "").strip().lower() == "sent":
        return "sent-by-me"
    if sender and sender in self_set:
        return "sent-by-me"
    if self_set & set(to_addrs):
        return "direct-to-me"
    if self_set & set(cc_addrs):
        return "cc-me"
    return "other"


def _derive_interaction_role(*, subject: str | None, folder_kind: str | None = None, from_addr: str | None, to_addrs: list[str], cc_addrs: list[str], self_addresses: set[str] | None) -> str:
    lowered = (subject or "").strip().casefold()
    self_role = _derive_self_role(folder_kind=folder_kind, from_addr=from_addr, to_addrs=to_addrs, cc_addrs=cc_addrs, self_addresses=self_addresses)
    if "[smartx info]" in lowered or from_addr in {"info@smartx.kr", "contacts@smartx.kr"}:
        return "broadcast"
    if lowered.startswith("fwd:") or lowered.startswith("fw:"):
        return "fyi-forward"
    if any(keyword in lowered for keyword in ["review", "검토", "proofreading"]):
        return "review-request"
    if any(keyword in lowered for keyword in ["status report 요청", "status 요청", "현황 요청", "상태 요청"]):
        return "status-request"
    if any(keyword in lowered for keyword in ["결정 부탁", "decision", "approve", "승인 부탁"]):
        return "decision-request"
    if self_role == "cc-me" and any(keyword in lowered for keyword in ["공유", "update", "진행", "상황"]):
        return "cc-for-awareness"
    if lowered.startswith("re:") and any(keyword in lowered for keyword in ["update", "thread", "weekly", "meeting", "미팅"]):
        return "team-thread-update"
    if self_role == "sent-by-me" and any(keyword in lowered for keyword in ["status", "보고", "제출", "reply", "re:"]):
        return "status-reply"
    if any(keyword in lowered for keyword in ["요청", "문의", "부탁", "확인", "작성", "submit"]):
        return "direct-ask"
    return "other"


def normalize_envelope(*, account: str, folder_kind: str, folder_name: str, envelope: dict, self_addresses: set[str] | None = None) -> dict:
    sender = envelope.get("from") or {}
    recipient = envelope.get("to") or {}
    to_addrs = _extract_addresses(envelope.get("to"))
    cc_addrs = _extract_addresses(envelope.get("cc"))
    source_id = str(envelope["id"])
    from_addr = sender.get("addr")
    to_addr = to_addrs[0] if to_addrs else (recipient.get("addr") if isinstance(recipient, dict) else None)
    return {
        "message_id": f"{account}:{folder_name}:{source_id}",
        "source_id": source_id,
        "account": account,
        "folder_kind": folder_kind,
        "folder_name": folder_name,
        "subject": envelope.get("subject"),
        "from_name": sender.get("name"),
        "from_addr": from_addr,
        "to_name": recipient.get("name") if isinstance(recipient, dict) else None,
        "to_addr": to_addr,
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "self_role": _derive_self_role(folder_kind=folder_kind, from_addr=from_addr, to_addrs=to_addrs, cc_addrs=cc_addrs, self_addresses=self_addresses),
        "interaction_role": _derive_interaction_role(folder_kind=folder_kind, from_addr=from_addr, subject=envelope.get("subject"), to_addrs=to_addrs, cc_addrs=cc_addrs, self_addresses=self_addresses),
        "date": envelope.get("date"),
        "flags": envelope.get("flags") or [],
        "has_attachment": bool(envelope.get("has_attachment")),
    }


def _default_runner(args: list[str]) -> str:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout


def build_fake_mail_runner(accounts: Iterable[str]) -> Callable[[list[str]], str]:
    account_set = set(accounts)

    def runner(args: list[str]) -> str:
        if len(args) >= 4 and args[:3] == ["himalaya", "folder", "list"]:
            account = args[-1]
            if account not in account_set:
                raise AssertionError(f"unexpected fake account: {account}")
            return "| NAME | DESC |\n|------|------|\n| INBOX | \\HasNoChildren |\n| [Gmail]/보낸편지함 | \\HasNoChildren, \\Sent |\n"

        if len(args) >= 8 and args[:3] == ["himalaya", "envelope", "list"]:
            account = args[4]
            if account not in account_set:
                raise AssertionError(f"unexpected fake account: {account}")
            if "--folder" in args:
                return json.dumps([
                    {
                        "id": "11",
                        "flags": ["Seen"],
                        "subject": f"Sent test for {account}",
                        "from": {"name": None, "addr": f"{account}@example.test"},
                        "to": {"name": None, "addr": "dest@example.test"},
                        "date": "2026-04-19 14:17+00:00",
                        "has_attachment": False,
                    }
                ], ensure_ascii=False)
            return json.dumps([
                {
                    "id": "10",
                    "flags": [],
                    "subject": f"Inbox test for {account}",
                    "from": {"name": "Tester", "addr": "tester@example.test"},
                    "to": {"name": None, "addr": f"{account}@example.test"},
                    "date": "2026-04-19 14:16+00:00",
                    "has_attachment": False,
                }
            ], ensure_ascii=False)

        raise AssertionError(f"unexpected fake command: {args}")

    return runner


def _strip_himalaya_warnings(output: str) -> str:
    lines = output.splitlines()
    kept = [line for line in lines if not re.match(r"^\d{4}-\d{2}-\d{2}T.*WARN ", line)]
    return "\n".join(kept).strip()


def _load_json_output(output: str) -> list[dict]:
    cleaned = _strip_himalaya_warnings(output)
    return json.loads(cleaned) if cleaned else []


def _load_checkpoints(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_checkpoints(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_file(snapshot_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return snapshot_dir / f"mail-{timestamp}.jsonl"


def _append_message_rows(database_path: Path, rows: Iterable[dict]) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO messages (
                    message_id, account, folder_kind, thread_key, subject, from_addr,
                    to_addrs, cc_addrs, self_role, interaction_role, sent_at, snippet, body_path, raw_json_path,
                    is_seen, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["message_id"],
                    row["account"],
                    row["folder_kind"],
                    None,
                    row.get("subject"),
                    row.get("from_addr"),
                    json.dumps(row.get("to_addrs") or [], ensure_ascii=False),
                    json.dumps(row.get("cc_addrs") or [], ensure_ascii=False),
                    row.get("self_role"),
                    row.get("interaction_role"),
                    row.get("date"),
                    None,
                    None,
                    None,
                    int("Seen" in row.get("flags", [])),
                    datetime.now(UTC).isoformat(),
                ),
            )
        conn.commit()


def collect_mail_snapshots(config: PipelineConfig, *, runner: Callable[[list[str]], str] | None = None) -> dict:
    runner = runner or _default_runner
    bootstrap_workspace(config)
    snapshot_path = _snapshot_file(config.mail_snapshot_dir)
    checkpoints = _load_checkpoints(config.checkpoints_path)
    checkpoints.setdefault("mail", {})
    all_rows: list[dict] = []
    account_summaries: list[dict] = []

    for account in config.accounts:
        folders = parse_folder_list_table(runner(["himalaya", "folder", "list", "-a", account]))
        sent_folder = choose_sent_folder(account, folders, config.sent_folder_overrides)

        inbox_rows = [
            normalize_envelope(account=account, folder_kind="inbox", folder_name="INBOX", envelope=item, self_addresses=set(config.self_addresses))
            for item in _load_json_output(
                runner([
                    "himalaya",
                    "envelope",
                    "list",
                    "-a",
                    account,
                    "--page-size",
                    str(config.mail_page_size),
                    "--output",
                    "json",
                ])
            )
        ]
        sent_rows = [
            normalize_envelope(account=account, folder_kind="sent", folder_name=sent_folder, envelope=item, self_addresses=set(config.self_addresses))
            for item in _load_json_output(
                runner([
                    "himalaya",
                    "envelope",
                    "list",
                    "-a",
                    account,
                    "--folder",
                    sent_folder,
                    "--page-size",
                    str(config.mail_page_size),
                    "--output",
                    "json",
                ])
            )
        ]
        rows = inbox_rows + sent_rows
        all_rows.extend(rows)
        checkpoints["mail"][account] = {
            "last_snapshot_file": snapshot_path.name,
            "sent_folder": sent_folder,
            "collected_at": datetime.now(UTC).isoformat(),
            "inbox_count": len(inbox_rows),
            "sent_count": len(sent_rows),
        }
        account_summaries.append(
            {
                "account": account,
                "sent_folder": sent_folder,
                "inbox_count": len(inbox_rows),
                "sent_count": len(sent_rows),
            }
        )

    snapshot_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_rows), encoding="utf-8")
    _append_message_rows(config.database_path, all_rows)
    _save_checkpoints(config.checkpoints_path, checkpoints)

    return {
        "snapshot_file": snapshot_path,
        "accounts": account_summaries,
        "total_messages": len(all_rows),
    }
