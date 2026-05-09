from pathlib import Path

from zeus_os.declarative import validate_repo_manifests


def test_discord_channel_manifest_is_declaration_only():
    app = validate_repo_manifests(Path.cwd()).apps["discord"]

    assert app.kind == "channel"
    assert app.runtime_bindings == ()
    assert app.legacy_scripts == ()
