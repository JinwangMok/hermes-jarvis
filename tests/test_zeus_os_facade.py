from __future__ import annotations

import os
import subprocess
import sys


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src = str((__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
    env["PYTHONPATH"] = src if not env.get("PYTHONPATH") else f"{src}{os.pathsep}{env['PYTHONPATH']}"
    return env


def test_canonical_zeus_os_import_facade() -> None:
    import zeus_os
    import zeus_os.config
    import zeus_os.runtime

    import zeus_os.queue
    import zeus_os.schema
    import zeus_os.worker

    assert zeus_os.__canonical_name__ == "zeus_os"
    assert zeus_os.config.PipelineConfig is not None
    assert zeus_os.runtime.run_pipeline_cycle is not None
    assert zeus_os.queue.enqueue is not None
    assert zeus_os.schema.apply_migrations is not None
    assert zeus_os.worker.run_deterministic_once is not None


def test_zeus_os_module_cli_uses_canonical_prog_name() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_os.cli", "--help"],
        check=False,
        text=True,
        env=_subprocess_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 0
    assert "usage: zeus-os" in completed.stdout


def test_legacy_cli_module_shows_canonical_zeus_prog_name() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_os.cli", "--help"],
        check=False,
        text=True,
        env=_subprocess_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 0
    assert "usage: zeus-os" in completed.stdout
