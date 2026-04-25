#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.helpers import output_text_path, transcription_endpoint

DEFAULT_SERVER_URL = os.environ.get('HERMES_LOCAL_STT_SERVER_URL', 'http://127.0.0.1:8177')
DEFAULT_MODEL = os.environ.get('HERMES_LOCAL_STT_MODEL', 'large-v3-turbo')
DEFAULT_TIMEOUT = int(os.environ.get('HERMES_LOCAL_STT_TIMEOUT', '60'))


def parse_response_text(response: requests.Response) -> str:
    content_type = response.headers.get('content-type', '')
    body = response.text.strip()
    if 'application/json' in content_type:
        payload = response.json()
        if isinstance(payload, dict):
            return str(payload.get('text', '')).strip()
        return body
    if body.startswith('{'):
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                return str(payload.get('text', '')).strip()
        except json.JSONDecodeError:
            pass
    return body


def transcribe_file(*, input_path: Path, output_dir: Path, language: str, model: str, server_url: str, timeout: int) -> Path:
    endpoint = transcription_endpoint(server_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_text_path(output_dir, input_path)
    with input_path.open('rb') as fh:
        response = requests.post(
            endpoint,
            data={
                'model': model,
                'language': language,
                'response_format': 'text',
                'temperature': '0',
            },
            files={'file': (input_path.name, fh, 'application/octet-stream')},
            timeout=timeout,
        )
    response.raise_for_status()
    output_path.write_text(parse_response_text(response), encoding='utf-8')
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Thin local_command client for Hermes local STT runtime.')
    parser.add_argument('--input', required=True, dest='input_path')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--language', default='')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--server-url', default=DEFAULT_SERVER_URL)
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    input_path = Path(args.input_path)
    if not input_path.is_file():
        raise SystemExit(f'Input file not found: {input_path}')

    output_path = transcribe_file(
        input_path=input_path,
        output_dir=Path(args.output_dir),
        language=args.language,
        model=args.model,
        server_url=args.server_url,
        timeout=args.timeout,
    )
    print(output_path)


if __name__ == '__main__':
    main()
