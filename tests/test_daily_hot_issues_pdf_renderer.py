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
    assert "항목" in html


def test_render_document_uses_report_masthead_and_newspaper_layout():
    md = """---
title: 테스트
---

# 오늘의 핫이슈 리포트 — 2026-04-26

- 기준 창: 오늘
- 해석 원칙: 원문 중심

## Executive Summary

중요한 원문 내용입니다.

### 1. OpenAI API 제공

- 원문 내용: API가 제공된다.
- 왜 중요한가: 도구 호출 검증이 필요하다.
"""
    doc = renderer.render_document(md, "2026-04-26 21:00 KST")
    assert "report-cover" in doc
    assert "body-grid" in doc
    assert "TODAY'S HOT ISSUES" in doc
    assert "오늘의 핫이슈 리포트" in doc
    assert "column-count: 2" in doc
    assert "issue-card" in doc
    assert "data-no=\"01\"" in doc
    assert "title: 테스트" not in doc
