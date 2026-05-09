#!/usr/bin/env python3
"""ZeusOS mail secretary cron wrapper.

Outputs only when there are newly reportable mail cases or degraded errors.
For new mail, it reports the content summary first, then asks approval for
preactive actions. Repeated old cases stay silent.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path('/home/jinwang/workspace/zeus-os')
CONFIG = 'config/pipeline.local.yaml'
STATE_FILE = REPO / 'state' / 'mail_secretary_watchdog_delivered.json'
NO_CASE = '신규로 허락 요청할 메일 case 없음.'

SECRET_PATTERNS = [
    re.compile(r'(?i)\b(authorization\s*:\s*bearer)\s+[^\s`\]})>,;]+'),
    re.compile(r'(?i)\b(bearer)\s+[^\s`\]})>,;]+'),
    re.compile(r'(?i)\b((?:api[_-]?key|token|password|passwd|secret)\s*[:=]\s*)[^\s`\]})>,;]+'),
    re.compile(r'(?i)\b((?:api[_-]?key|token|password|passwd|secret)\s+)\S+'),
    re.compile(r'\bsk-[A-Za-z0-9_-]{8,}\b'),
]


def redact(value: Any) -> str:
    text = '' if value is None else str(value)
    for pattern in SECRET_PATTERNS:
        def repl(match: re.Match[str]) -> str:
            if match.lastindex:
                return f"{match.group(1)} [REDACTED]"
            return '[REDACTED]'
        text = pattern.sub(repl, text)
    return text


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO,
        env={**os.environ, 'PYTHONPATH': 'src'},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=240,
    )


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {'delivered_cases': {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = -1
    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f'.{STATE_FILE.name}.',
            suffix='.json',
            dir=STATE_FILE.parent,
            text=True,
        )
        tmp_path = Path(tmp_name)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            fd = -1
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, STATE_FILE)
    finally:
        if fd != -1:
            os.close(fd)
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass


def database_path() -> Path:
    return REPO / 'state' / 'personal_intel.db'


def message_meta(message_ids: list[str]) -> dict[str, dict[str, str]]:
    if not message_ids:
        return {}
    placeholders = ','.join('?' for _ in message_ids)
    query = f"SELECT message_id, from_addr, subject, sent_at, snippet FROM messages WHERE message_id IN ({placeholders})"
    with sqlite3.connect(database_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, message_ids).fetchall()
    return {row['message_id']: {k: row[k] or '' for k in ('from_addr', 'subject', 'sent_at', 'snippet')} for row in rows}


def case_fingerprint(case: dict[str, Any]) -> str:
    parts = [
        case.get('case_id', ''),
        case.get('source_message_id', ''),
        case.get('status', ''),
        case.get('triage_kind', ''),
        case.get('action_type', ''),
        case.get('risk_level', ''),
        case.get('meaning_summary', ''),
        case.get('body_excerpt', ''),
        case.get('approval_card_md', ''),
    ]
    return '|'.join(str(part) for part in parts)


def render_new_cases(cases: list[dict[str, Any]]) -> str:
    meta = message_meta([str(case.get('source_message_id', '')) for case in cases])
    lines = [f"📬 새 메일 {len(cases)}건"]
    action_cards: list[str] = []
    for idx, case in enumerate(cases, 1):
        mid = str(case.get('source_message_id', ''))
        m = meta.get(mid, {})
        sender = redact(m.get('from_addr') or '(sender unknown)')
        subject = redact(m.get('subject') or '(제목 없음)')
        excerpt = redact(case.get('body_excerpt') or m.get('snippet') or '').strip()
        if len(excerpt) > 260:
            excerpt = excerpt[:257] + '...'
        action = redact(case.get('action_type') or 'read_only')
        risk = redact(case.get('risk_level') or 'none')
        triage = redact(case.get('triage_kind') or 'unknown')
        next_action = redact(case.get('next_action_text') or '추가 행동은 보류합니다.')
        lines.extend([
            '',
            f"{idx}. {sender} / {subject}",
            f"- 내용: {excerpt or redact(case.get('meaning_summary') or '본문 요약 근거가 부족합니다.')}",
            f"- 판단: {triage} · action={action} · risk={risk}",
            f"- 다음: {next_action}",
        ])
        card = redact(case.get('approval_card_md') or '').strip()
        if card:
            action_cards.append(card)
    if action_cards:
        lines.extend(['', '제가 preactive하게 준비 가능한 대응입니다. 진행할까요?', ''])
        lines.extend(action_cards)
    return '\n'.join(lines).strip()


def degraded(step: str, proc: subprocess.CompletedProcess[str]) -> int:
    err = redact(proc.stderr or proc.stdout or '').strip()[:1800]
    print(f"[ZeusOS 메일 비서 degraded]\n- 단계: {step}\n- 오류:\n```\n{err}\n```")
    return 0


def main() -> int:
    triage = run([
        sys.executable, '-m', 'zeus_os.cli', 'secretary-triage',
        '--config', CONFIG,
        '--since-minutes', '30',
        '--limit', '20',
        '--json',
    ])
    if triage.returncode != 0:
        return degraded('secretary-triage', triage)

    try:
        payload = json.loads(triage.stdout)
        artifact_path = Path(payload['artifact_path'])
        artifact = json.loads(artifact_path.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f"[ZeusOS 메일 비서 degraded]\n- 단계: triage-artifact-read\n- 오류: {redact(exc)}")
        return 0

    cases = artifact.get('cases') or []
    if not cases:
        return 0

    state = load_state()
    delivered = state.setdefault('delivered_cases', {})
    new_cases: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get('case_id') or case.get('source_message_id') or '')
        fingerprint = case_fingerprint(case)
        if delivered.get(case_id) != fingerprint:
            new_cases.append(case)
            delivered[case_id] = fingerprint

    if not new_cases:
        save_state(state)
        return 0

    print(render_new_cases(new_cases))
    save_state(state)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
