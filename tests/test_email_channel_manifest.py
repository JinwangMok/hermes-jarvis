from pathlib import Path

from zeus_os.declarative import validate_repo_manifests


def test_emails_channel_manifest_is_declaration_only():
    app = validate_repo_manifests(Path.cwd()).apps["emails"]

    assert app.kind == "channel"
    assert app.runtime_bindings == ()
    assert app.legacy_scripts == ()
