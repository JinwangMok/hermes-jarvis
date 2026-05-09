from pathlib import Path

from zeus_os.declarative import validate_repo_manifests


CUSTOM_DEFINED_TOOL_NAMES = (
    "tmux-manager",
    "opencode-manager",
    "claude-code-manager",
)


def test_custom_defined_tool_manifests_are_declaration_only_tools():
    result = validate_repo_manifests(Path.cwd())

    for name in CUSTOM_DEFINED_TOOL_NAMES:
        assert name in result.apps
        app = result.apps[name]
        assert app.kind == "tool"
        assert app.runtime_bindings == ()
        assert app.legacy_scripts == ()
