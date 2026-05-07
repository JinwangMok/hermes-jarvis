from pathlib import Path


_FORBIDDEN_PATH_TOKENS = (
    "/home/jinwang/workspace/jinwang-jarvis",
    "~/workspace/jinwang-jarvis",
    "workspace/jinwang-jarvis/",
)


def test_zeus_source_has_no_hardcoded_personal_workspace_path():
    repo_root = Path(__file__).resolve().parents[1]
    zeus_dir = repo_root / "src" / "jinwang_jarvis" / "zeus_os"
    hits: list[str] = []

    for source in sorted(zeus_dir.rglob("*.py")):
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if any(token in line for token in _FORBIDDEN_PATH_TOKENS):
                hits.append(f"{source.relative_to(repo_root)}:{line_number}: {line.strip()}")

    assert not hits, "Hardcoded personal workspace paths found in Zeus source:\n" + "\n".join(hits)
