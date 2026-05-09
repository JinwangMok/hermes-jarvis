from pathlib import Path

from zeus_os.declarative import validate_repo_manifests


def test_email_sender_manifest_is_declaration_only_tool():
    app = validate_repo_manifests(Path.cwd()).apps["email-sender"]

    assert app.kind == "tool"
    assert app.runtime_bindings == ()
    assert app.legacy_scripts == ()
