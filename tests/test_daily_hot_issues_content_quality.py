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


def test_daily_hot_issues_linter_rejects_internal_ops_as_main_issue():
    md = """# 오늘의 핫이슈

- 범위: 최근 24시간, 낮춘 기준 적용 + Jarvis 운영 보강 반영

## 주요 이슈

### Jarvis 운영 보강: 복지로와 IRIS AI 대학 과제를 매일 확인 대상으로 고정
- 확인된 사실: Jarvis 코드가 업데이트되어 복지로와 IRIS를 우선 확인하도록 바뀌었다. 해당 변경은 GitHub에 커밋·푸시됐다.
- 왜 중요한가: 정책·청년·복지·R&D 정보는 한 번 놓치면 신청 기간을 잃을 수 있다.
- 오늘 할 일: 복지로와 IRIS 자동 확인 결과를 본다.
- 근거: GitHub 변경 커밋. 복지로 공식 경로: https://www.bokjiro.go.kr/ssis-tbu/index.do . IRIS 공식 경로: https://www.iris.go.kr/ .
- 불확실성: 자동 보고에서는 신청 가능 여부를 확정하지 않는다.
"""
    errors = linter.lint_text(md)
    joined = "\n".join(errors)
    assert "internal ops" in joined
    assert "낮춘 기준" in joined


def test_daily_hot_issues_linter_requires_source_trust_label_not_generic_fact_label():
    md = """# 오늘의 핫이슈

## 주요 이슈

### AI agent가 production database를 삭제했다는 사례가 확산
- 확인된 사실: X 게시물에 따르면 AI agent가 production database를 삭제했다.
- 왜 중요한가: agent 권한 정책을 점검해야 한다.
- 오늘 할 일: 사례를 권한 정책 메모에 기록한다.
- 근거: https://x.com/example/status/1, 2026-04-27 확인.
- 불확실성: 실제 사고인지, 실험인지, 과장인지 검증되지 않았다.
"""
    errors = linter.lint_text(md)
    assert any("출처 성격" in err for err in errors)


def test_daily_hot_issues_linter_rejects_opportunity_without_direct_notice_contract():
    md = """# 오늘의 핫이슈

## 주요 이슈

### IRIS AI 기반 대학 과학기술 혁신사업 신규과제 공모 확인 필요
- 출처 성격: 공식 공고 후보.
- 확인된 사실: IRIS에서 AI 기반 대학 과학기술 혁신사업 관련 공고를 확인 대상으로 올렸다.
- 왜 중요한가: GIST AI 인프라 RFP와 연결될 수 있다.
- 오늘 할 일: 신청 가능성을 검토한다.
- 근거: https://www.iris.go.kr/ , 2026-04-27 확인.
- 불확실성: 세부 자격은 아직 확인되지 않았다.
"""
    errors = linter.lint_text(md)
    joined = "\n".join(errors)
    assert "opportunity" in joined
    assert "deadline/window" in joined



def test_daily_hot_issues_linter_rejects_source_type_prefix_spoofing():
    md = """# 오늘의 핫이슈

## 주요 이슈

### 출처 라벨이 모호한 항목
- 출처 성격: 공식 발표 후보.
- 확인된 사실: 어떤 발표가 있었다.
- 왜 중요한가: 후속 확인이 필요하다.
- 오늘 할 일: 원문을 확인한다.
- 근거: https://example.com/source, 2026-04-27 확인.
- 불확실성: 세부 내용은 미확인이다.
"""
    errors = linter.lint_text(md)
    assert any("unclear 출처 성격" in err for err in errors)


def test_daily_hot_issues_linter_rejects_internal_ops_even_if_ops_section_exists_elsewhere():
    md = """# 오늘의 핫이슈

## 운영 메모

### 내부 자동화 변경
- 출처 성격: 내부 운영 변경.
- 확인된 사실: Jarvis 내부 cron 설명이 별도 운영 메모에 있다.
- 왜 중요한가: 독자에게는 외부 이슈와 분리되어야 한다.
- 오늘 할 일: 운영자는 별도 로그를 확인한다.
- 근거: https://github.com/example/repo/commit/1, 2026-04-27 확인.
- 불확실성: 외부 핫이슈가 아니다.

## 주요 이슈

### Jarvis 운영 보강이 외부 핫이슈처럼 반복 노출됨
- 출처 성격: 보도.
- 확인된 사실: Jarvis 코드가 업데이트되어 GitHub에 커밋·푸시됐다.
- 왜 중요한가: 내부 운영 변경이다.
- 오늘 할 일: 외부 핫이슈로 보내지 않는다.
- 근거: https://github.com/example/repo/commit/2, 2026-04-27 확인.
- 불확실성: 외부 사건이 아니다.
"""
    errors = linter.lint_text(md)
    assert any("mix internal ops" in err for err in errors)


def test_daily_hot_issues_linter_accepts_reader_facing_issue_card():
    md = """# 오늘의 핫이슈

## 주요 이슈

### 과기정통부·교육부, AI 인재양성 TF 출범…후속 공고 확인 필요
- 출처 성격: 보도.
- 확인된 사실: 과기정통부와 교육부가 AI 인재양성 전담 TF를 출범했다는 보도가 나왔다.
- 왜 중요한가: 대학·연구실·교육사업 대상 후속 공고가 나올 경우 AI/cloud 연구와 연결될 수 있다.
- 오늘 할 일: IITP, NRF, NIPA 신규 공고에서 AI, cloud, SW, 대학원생 키워드를 확인한다.
- 근거: 보도 IT비즈뉴스, https://example.com/article, 2026-04-26 확인.
- 불확실성: 아직 신청 가능한 공식 공고, 예산, 마감일, 지원대상/자격은 확인되지 않았다.
"""
    assert linter.lint_text(md) == []
