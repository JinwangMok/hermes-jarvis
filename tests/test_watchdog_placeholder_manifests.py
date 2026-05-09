from pathlib import Path

from zeus_os.declarative import validate_repo_manifests


PLACEHOLDER_WATCHDOGS = (
    "journal-to-wiki",
    "compact-knowledge-base",
    "dialog-pattern-analysis",
    "update-handler",
)


def test_watchdog_placeholder_manifests_are_declaration_only():
    result = validate_repo_manifests(Path.cwd())

    for name in PLACEHOLDER_WATCHDOGS:
        app = result.apps[name]
        assert app.kind == "watchdog"
        assert app.runtime_bindings == ()
        assert app.legacy_scripts == ()
