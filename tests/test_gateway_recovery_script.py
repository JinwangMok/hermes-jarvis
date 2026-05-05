import json
import os
import subprocess
from pathlib import Path


def test_gateway_recovery_script_dry_run_prefers_systemd_run(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "arm-opencode-gateway-recovery.sh"
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["HERMES_GATEWAY_RECOVERY_HOOK_DRY_RUN"] = "1"

    result = subprocess.run(
        [str(script), "pytest-dry-run"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["would_arm"] is True
    assert payload["launcher"] == "systemd-run"
    assert payload["unit"].startswith("opencode-gateway-recovery-")
    assert payload["session"].startswith("oc-gw-recover-")
    assert str(tmp_path / ".hermes" / "recovery") in payload["run_dir"]

    latest = tmp_path / ".hermes" / "recovery" / "latest-systemd-arm.txt"
    latest_text = latest.read_text(encoding="utf-8")
    assert "unit=opencode-gateway-recovery-" in latest_text
    assert "trigger=pytest-dry-run" in latest_text
