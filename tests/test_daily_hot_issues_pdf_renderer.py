from pathlib import Path

import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_daily_hot_issues_pdf.py"


spec = importlib.util.spec_from_file_location("render_daily_hot_issues_pdf", SCRIPT)
renderer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(renderer)


def test_strip_yaml_frontmatter_before_pdf_html_rendering():
    md = """---
title: 테스트
created: 2026-04-26
---

# 본문 제목

- 항목
"""
    html = renderer.markdown_to_html(md)
    assert "title: 테스트" not in html
    assert "created: 2026-04-26" not in html
    assert "본문 제목" in html
    assert "항목" in html
