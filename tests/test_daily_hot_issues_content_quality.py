import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint_daily_hot_issues_content.py"

spec = importlib.util.spec_from_file_location("lint_daily_hot_issues_content", SCRIPT)
linter = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(linter)


def test_daily_hot_issues_linter_rejects_vague_internal_signal_language():
    md = """# 오늘의 핫이슈

## 주요 이슈

### 국내 AI 인재양성 정책 신호
- 성격: high-heat 공식 신호.
- 내용 분석: 후속 공고 감시가 필요하다.
"""
    errors = linter.lint_text(md)
    joined = "\n".join(errors)
    assert "신호" in joined
    assert "high-heat" in joined
    assert "missing fields" in joined


def test_daily_hot_issues_linter_accepts_reader_facing_issue_card():
    md = """# 오늘의 핫이슈

## 주요 이슈

### 과기정통부·교육부, AI 인재양성 TF 출범…후속 공고 확인 필요
- 확인된 사실: 과기정통부와 교육부가 AI 인재양성 전담 TF를 출범했다는 보도가 나왔다.
- 왜 중요한가: 대학·연구실·교육사업 대상 후속 공고가 나올 경우 AI/cloud 연구와 연결될 수 있다.
- 오늘 할 일: IITP, NRF, NIPA 신규 공고에서 AI, cloud, SW, 대학원생 키워드를 확인한다.
- 근거: 보도 IT비즈뉴스, https://example.com/article, 2026-04-26 확인.
- 불확실성: 아직 신청 가능한 공식 공고, 예산, 마감일은 확인되지 않았다.
"""
    assert linter.lint_text(md) == []
