"""Canonical ZeusOS CLI entrypoint."""

from __future__ import annotations

from collections.abc import Sequence

from jinwang_jarvis.cli import main as _legacy_main


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ZeusOS CLI using the canonical program name."""

    return _legacy_main(argv, prog="zeus-os")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
