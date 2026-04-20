from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .bootstrap import bootstrap_workspace
from .config import PipelineConfig

ROLE_MAP = {
    "Professor": "advisor",
    "Research Professor": "research-professor",
    "Ph.D. Student": "phd-student",
    "M.S. Student": "ms-student",
    "Intern": "intern",
    "(Integrated)": "ms-student",
}

PRIORITY_BY_ROLE = {
    "advisor": 100,
    "research-professor": 60,
    "phd-student": 25,
    "ms-student": 20,
    "intern": 10,
    "self": 90,
    "lab-member": 20,
    "external": 0,
}

ADVISOR_STRONG_ACTION_HINTS = (
    "요청",
    "문의",
    "확인",
    "검토",
    "제출",
    "준비",
    "협조",
    "reply",
    "review",
    "confirm",
    "submit",
    "please",
)
ADVISOR_MEETING_HINTS = (
    "agenda",
    "meeting",
    "미팅",
    "회의",
)
ADVISOR_FYI_HINTS = (
    "fwd:",
    "fw:",
    "소개자료",
    "summit",
    "speaker",
    "초대",
    "초대장",
    "사업설명회",
    "안내",
    "공지",
    "자료 공유",
    "공유드립니다",
)
ADVISOR_REPORT_FYI_HINTS = (
    "보고",
    "보고드립니다",
    "진행 현황",
    "현황",
    "업데이트",
    "update",
)


def parse_sender_map_markdown(markdown: str) -> dict[str, dict]:
    identities: dict[str, dict] = {}
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        if "|" in line and "@" in line:
            parts = [part.strip() for part in line[2:].split("|")]
            if len(parts) < 3:
                continue
            role = ROLE_MAP.get(parts[0], parts[0].strip().casefold())
            display_name = parts[1]
            emails = [email.strip() for email in parts[2].split("/") if "@" in email]
            for email in emails:
                normalized = email.strip().lower()
                mapped_role = "self" if normalized in {"jinwang@smartx.kr", "jinwangmok@gm.gist.ac.kr", "jinwangmok@gmail.com"} else role
                identities[normalized] = {
                    "email": normalized,
                    "display_name": display_name,
                    "role": mapped_role,
                    "organization": _infer_organization(normalized),
                    "priority_base": PRIORITY_BY_ROLE.get(mapped_role, 0),
                }
        else:
            for email in re.findall(r"`([^`]+@[^`]+)`", line):
                normalized = email.lower()
                identities[normalized] = {
                    "email": normalized,
                    "display_name": email,
                    "role": "advisor",
                    "organization": _infer_organization(normalized),
                    "priority_base": PRIORITY_BY_ROLE["advisor"],
                }
    return identities


def _infer_organization(email: str) -> str:
    domain = email.split("@", 1)[-1].lower()
    if domain.endswith("smartx.kr"):
        return "smartx"
    if domain.endswith("gist.ac.kr") or domain.endswith("gm.gist.ac.kr"):
        return "gist"
    if domain.endswith("gmail.com"):
        return "gmail"
    return domain


def resolve_sender_identity(email: str | None, sender_map: dict[str, dict]) -> dict:
    normalized = (email or "").strip().lower()
    if normalized in sender_map:
        return dict(sender_map[normalized])
    if normalized.endswith("@smartx.kr"):
        return {"email": normalized, "display_name": normalized, "role": "lab-member", "organization": "smartx", "priority_base": PRIORITY_BY_ROLE["lab-member"]}
    if normalized.endswith("@gm.gist.ac.kr") or normalized.endswith("@gist.ac.kr"):
        return {"email": normalized, "display_name": normalized, "role": "lab-member", "organization": "gist", "priority_base": PRIORITY_BY_ROLE["lab-member"]}
    return {"email": normalized, "display_name": normalized, "role": "external", "organization": _infer_organization(normalized) if normalized else "unknown", "priority_base": PRIORITY_BY_ROLE["external"]}


def classify_message(message: dict, sender_map: dict[str, dict]) -> dict:
    sender_identity = resolve_sender_identity(message.get("from_addr"), sender_map)
    subject = (message.get("subject") or "").strip()
    lowered = subject.casefold()
    labels: list[dict] = []

    def add_label(label: str, score: float, reason: dict) -> None:
        labels.append({"label": label, "score": score, "reason": reason})

    role = sender_identity["role"]
    if role == "advisor":
        if any(hint in lowered for hint in ADVISOR_REPORT_FYI_HINTS) and not any(hint in lowered for hint in ADVISOR_STRONG_ACTION_HINTS):
            add_label("advisor-fyi", 35.0, {"role": role, "from_addr": message.get("from_addr"), "mode": "report-fyi"})
        elif any(hint in lowered for hint in ADVISOR_FYI_HINTS) and not any(hint in lowered for hint in ADVISOR_STRONG_ACTION_HINTS):
            add_label("advisor-fyi", 35.0, {"role": role, "from_addr": message.get("from_addr"), "mode": "fyi"})
        elif any(hint in lowered for hint in ADVISOR_STRONG_ACTION_HINTS):
            add_label("advisor-request", 100.0, {"role": role, "from_addr": message.get("from_addr"), "mode": "action"})
        elif any(hint in lowered for hint in ADVISOR_MEETING_HINTS) and not any(hint in lowered for hint in ADVISOR_FYI_HINTS):
            add_label("advisor-request", 90.0, {"role": role, "from_addr": message.get("from_addr"), "mode": "meeting"})
        elif any(hint in lowered for hint in ADVISOR_FYI_HINTS):
            add_label("advisor-fyi", 35.0, {"role": role, "from_addr": message.get("from_addr"), "mode": "fyi"})
        else:
            add_label("advisor-request", 70.0, {"role": role, "from_addr": message.get("from_addr"), "mode": "default"})
    elif role in {"research-professor", "lab-member", "phd-student", "ms-student", "intern"}:
        add_label("lab", 30.0, {"role": role})

    if "security alert" in lowered or "review your google account settings" in lowered:
        add_label("security-routine", 20.0, {"matched": "security"})
    if re.search(r"(?:\[ta\]|\bta\b|조교)", lowered):
        add_label("ta", 35.0, {"matched": "ta"})
    if any(keyword in lowered for keyword in ("meeting", "agenda", "zoom", "미팅", "세미나")):
        add_label("meeting", 40.0, {"matched": "meeting-keyword"})
    if any(keyword in lowered for keyword in ("vendor", "solution", "demo", "conference", "event", "광고")):
        add_label("promotional-reference", 15.0, {"matched": "promo-keyword"})
    if message.get("account") == "smartx":
        add_label("work-account", 10.0, {"account": "smartx"})

    labels.sort(key=lambda item: (-item["score"], item["label"]))
    return {"sender_identity": sender_identity, "labels": labels}


def _load_sender_map(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}
    return parse_sender_map_markdown(path.read_text(encoding="utf-8"))


def _upsert_sender_identities(database_path: Path, identities: dict[str, dict], source_note: str | None) -> None:
    with sqlite3.connect(database_path) as conn:
        for identity in identities.values():
            conn.execute(
                """
                INSERT OR REPLACE INTO sender_identities (email, display_name, role, organization, priority_base, source_note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    identity["email"],
                    identity["display_name"],
                    identity["role"],
                    identity.get("organization"),
                    identity.get("priority_base", 0),
                    source_note,
                ),
            )
        conn.commit()


def _load_messages(database_path: Path) -> list[dict]:
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT message_id, account, folder_kind, subject, from_addr FROM messages ORDER BY message_id").fetchall()
    return [dict(row) for row in rows]


def _replace_message_labels(database_path: Path, labels_by_message: dict[str, list[dict]]) -> None:
    with sqlite3.connect(database_path) as conn:
        conn.execute("DELETE FROM message_labels")
        for message_id, labels in labels_by_message.items():
            for label in labels:
                conn.execute(
                    "INSERT INTO message_labels (message_id, label, score, reason_json) VALUES (?, ?, ?, ?)",
                    (message_id, label["label"], label["score"], json.dumps(label["reason"], ensure_ascii=False)),
                )
        conn.commit()


def classify_messages(config: PipelineConfig) -> dict:
    bootstrap_workspace(config)
    sender_map = _load_sender_map(config.sender_map_path)
    _upsert_sender_identities(config.database_path, sender_map, str(config.sender_map_path) if config.sender_map_path else None)
    messages = _load_messages(config.database_path)
    labels_by_message: dict[str, list[dict]] = {}
    for message in messages:
        result = classify_message(message, sender_map)
        labels_by_message[message["message_id"]] = result["labels"]
    _replace_message_labels(config.database_path, labels_by_message)
    checkpoints = {}
    if config.checkpoints_path.exists():
        checkpoints = json.loads(config.checkpoints_path.read_text(encoding="utf-8"))
    checkpoints.setdefault("classification", {})
    checkpoints["classification"]["messages"] = {
        "classified_at": datetime.now(UTC).isoformat(),
        "message_count": len(messages),
        "identity_count": len(sender_map),
    }
    config.checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"message_count": len(messages), "identity_count": len(sender_map)}
