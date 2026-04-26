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


def test_render_document_excludes_internal_appendix_and_local_paths():
    md = """# 오늘의 핫이슈 리포트 — 2026-04-26

## 주요 이슈

### 공식 발표
- 확인된 사실: 공개 발표가 있었다.
- 왜 중요한가: 후속 확인이 필요하다.
- 오늘 할 일: 공식 원문을 확인한다.

## 부록: 내부 생성 근거
- source: /home/jinwang/workspace/jinwang-jarvis/data/internal.json
- source audit: internal
"""
    doc = renderer.render_document(md, "2026-04-26 21:00 KST")
    assert "부록: 내부 생성 근거" not in doc
    assert "/home/jinwang" not in doc
    assert "source audit" not in doc
    assert "매일 핵심 이슈 브리핑" in doc
    assert "SECTION" not in doc
