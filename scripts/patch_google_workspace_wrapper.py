#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import sys

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
TARGET = HERMES_HOME / "skills" / "productivity" / "google-workspace" / "scripts" / "google_api.py"

OLD_GWS_ENV = '''def _gws_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = str(TOKEN_PATH)
    return env
'''

NEW_GWS_ENV = '''def _gws_env() -> dict[str, str]:
    env = os.environ.copy()
    if TOKEN_PATH.exists():
        env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = str(TOKEN_PATH)
    return env
'''

OLD_RUN_GWS = '''def _run_gws(parts: list[str], *, params: dict | None = None, body: dict | None = None):
    binary = _gws_binary()
    if not binary:
        raise RuntimeError("gws not installed")

    _ensure_authenticated()

    cmd = [binary, *parts]
'''

NEW_RUN_GWS = '''def _run_gws(parts: list[str], *, params: dict | None = None, body: dict | None = None):
    binary = _gws_binary()
    if not binary:
        raise RuntimeError("gws not installed")

    env = _gws_env()
    if TOKEN_PATH.exists():
        _ensure_authenticated()

    cmd = [binary, *parts]
'''

OLD_ENV_CALL = '''    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=_gws_env(),
    )
'''

NEW_ENV_CALL = '''    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )
'''


def main() -> int:
    if not TARGET.exists():
        print(f"Target not found: {TARGET}", file=sys.stderr)
        return 1

    text = TARGET.read_text(encoding="utf-8")
    updated = text

    if NEW_GWS_ENV not in updated:
        if OLD_GWS_ENV not in updated:
            print("Could not find _gws_env() snippet to patch", file=sys.stderr)
            return 2
        updated = updated.replace(OLD_GWS_ENV, NEW_GWS_ENV)

    if NEW_RUN_GWS not in updated:
        if OLD_RUN_GWS not in updated:
            print("Could not find _run_gws() auth snippet to patch", file=sys.stderr)
            return 3
        updated = updated.replace(OLD_RUN_GWS, NEW_RUN_GWS)

    if NEW_ENV_CALL not in updated:
        if OLD_ENV_CALL not in updated:
            print("Could not find subprocess env snippet to patch", file=sys.stderr)
            return 4
        updated = updated.replace(OLD_ENV_CALL, NEW_ENV_CALL)

    if updated != text:
        TARGET.write_text(updated, encoding="utf-8")
        print(f"Patched {TARGET}")
    else:
        print(f"Already patched {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
