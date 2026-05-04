import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint_daily_hot_issues_content.py"

spec = importlib.util.spec_from_file_location("lint_daily_hot_issues_content", SCRIPT)
assert spec is not None
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


def test_daily_hot_issues_linter_accepts_agent_os_community_issue_with_hermes_mention():
    md = """# 오늘의 핫이슈

## 주요 이슈

### Agent OS
- 출처 성격: 커뮤니티 소개.
- 확인된 사실: Ouroboros가 Agent OS로 진화 중이며 Claude, Codex, Hermes를 이용한 실제 데모와 공개 목표를 언급했다.
- 왜 중요한가: Agent OS와 에이전트 실행 방식 변화가 연구 harness 설계와 로컬 에이전트 운영 기준에 직접 영향을 줍니다.
- 오늘 할 일: 원문에서 실제 데모 내용, 공개된 repo, 릴리스 목표가 무엇인지 확인합니다.
- 근거: [원문 링크](https://github.com/Q00/ouroboros), 2026-05-03 확인.
- 불확실성: 커뮤니티 게시물 기반이므로 실제 공개 범위와 릴리스 상태는 원문·저장소에서 재확인해야 합니다.
"""
    errors = linter.lint_text(md)
    joined = "\n".join(errors)
    assert "mix internal ops" not in joined
    assert "unclear 출처 성격" not in joined
    assert "신호" not in joined


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


def test_daily_hot_issues_linter_rejects_empty_main_issue_section_even_with_news_briefs():
    md = """# 오늘의 핫이슈

## 주요 이슈

## 뉴스 카테고리별 브리핑

### 기술
- 출처 성격: 보도.
- 확인된 사실: 기술 분야 기사가 수집됐다.
- 왜 중요한가: 기술 흐름 확인용이다.
- 오늘 할 일: 원문을 확인한다.
- 근거: https://example.com/news, 2026-05-03 확인.
- 불확실성: 세부 영향은 단정하지 않는다.
"""
    errors = linter.lint_text(md)
    assert any("주요 이슈" in err and "no reader-facing issue cards" in err for err in errors)


def test_daily_hot_issues_linter_rejects_provider_boilerplate_as_reader_fact():
    md = """# 오늘의 핫이슈

## 주요 이슈

### AI agent release
- 출처 성격: 공식 발표.
- 확인된 사실: 본 공지는 AI agent가 새 API를 공개하고 2026년 5월부터 베타 이용자를 받는다고 설명합니다.
- 왜 중요한가: 새 API는 연구 자동화에서 도구 권한과 승인 지점을 다시 설계해야 하는 실제 변경입니다.
- 오늘 할 일: 공식 문서에서 적용 대상 API, 권한 승인 방식, 기존 정책과 달라진 문구를 비교합니다.
- 근거: [공식 문서](https://example.com/agent-api), 2026-05-03 확인.
- 불확실성: 세부 요금과 적용 지역은 원문에서 다시 확인해야 합니다.

## 뉴스 카테고리별 브리핑

### 정치
- 출처 성격: 보도.
- 확인된 사실: 기사 섹션 정보가 정치/선거를 포함하는 경우 정치/선거섹션 정책이 적용됩니다.
- 왜 중요한가: 기사 섹션 정보 문구는 원문 사건이 아니라 포털 안내문입니다.
- 오늘 할 일: Naver News 원문에서 사건 본문을 확인합니다.
- 근거: [Naver News](https://n.news.naver.com/mnews/article/001/0000000000), 2026-05-03 확인.
- 불확실성: 자동 추출 요약입니다.
"""

    errors = linter.lint_text(md)

    assert any("provider boilerplate" in error for error in errors)


def test_daily_hot_issues_linter_accepts_explicit_no_promoted_main_issue_with_news_briefs():
    md = """# 오늘의 핫이슈

## 주요 이슈

- 승격된 주요 이슈 없음: 원문 내용과 독자 행동 근거가 충분한 항목이 없어 이 섹션은 비워 두고, 확인 가능한 뉴스 브리핑만 제공합니다.

## 뉴스 카테고리별 브리핑

### 기술
- 출처 성격: 보도.
- 확인된 사실: 본 기사는 한국은행이 올해 경제 성장률 전망을 낮추고 반도체 수출 회복에도 내수 부진이 성장률을 제약한다고 설명했다는 내용을 다뤘다.
- 왜 중요한가: 성장률 전망 하향은 정책당국이 수출 회복만으로 경기 반등을 확신하지 않는다는 뜻이라 예산·R&D·기업 투자 판단의 전제치를 낮춰 잡아야 합니다.
- 오늘 할 일: 원문에서 성장률 조정 폭, 내수 부진 근거, 다음 전망 수정 시점을 확인합니다.
- 근거: https://example.com/news, 2026-05-03 확인.
- 불확실성: 기사 요약이므로 실제 수치와 발언 맥락은 원문 표와 인용문으로 재확인해야 합니다.
"""
    assert linter.lint_text(md) == []


def test_daily_hot_issues_linter_rejects_unverified_candidate_wrapped_as_main_issue():
    md = """# 오늘의 핫이슈

## 주요 이슈

### Our podcast is live!... Ouroboros...
- 출처 성격: 검증 전 후보.
- 확인된 사실: watch 후보에 항목이 들어왔다.
- 왜 중요한가: 분류: AI · 열기: low · 중요도 0.620 · 모멘텀 0.000
- 오늘 할 일: 원문을 확인한다.
- 근거: https://example.com/post, 2026-05-03 확인.
- 불확실성: 후보 단계라 외부 이슈인지 검증되지 않았다.
"""
    errors = linter.lint_text(md)
    joined = "\n".join(errors)
    assert "검증 전 후보" in joined
    assert "internal scoring" in joined or "scoring" in joined


def test_daily_hot_issues_linter_rejects_keyword_only_main_issue_without_reader_value():
    md = """# 오늘의 핫이슈

## 주요 이슈

### AI agent / Kubernetes / 논문 키워드가 함께 언급됨
- 출처 성격: 보도.
- 확인된 사실: AI agent, Kubernetes, 논문 관련 항목이 수집됐습니다.
- 왜 중요한가: 기술 분야의 정책·시장·사회 흐름을 원문 기준으로 확인하기 위한 독자용 브리핑입니다.
- 오늘 할 일: 제목만으로 판단하지 말고 원문을 확인합니다.
- 근거: https://example.com/article, 2026-05-03 확인.
- 불확실성: 수집 요약이므로 제목만으로 사실관계나 영향 범위를 단정하지 않습니다.
"""
    errors = linter.lint_text(md)
    joined = "\n".join(errors)
    assert "keyword-only" in joined or "reader value" in joined
    assert "generic why-it-matters" in joined


def test_daily_hot_issues_linter_rejects_thin_confirmed_fact_that_only_says_collected():
    md = """# 오늘의 핫이슈

## 주요 이슈

### CNCF 블로그에서 AI sandboxing 글이 수집됨
- 출처 성격: 공식 블로그.
- 확인된 사실: CNCF 블로그에서 AI sandboxing 항목이 수집됐습니다.
- 왜 중요한가: Kubernetes 운영에서 AI 워크로드 격리와 정책 집행이 실제 클러스터 설계 이슈로 올라오고 있어 Playbox/KARVIS의 보안·권한 모델 점검 항목과 직접 연결됩니다.
- 오늘 할 일: 원문에서 제안하는 격리 경계, 런타임 전제, Kubernetes 정책 컴포넌트를 확인합니다.
- 근거: https://www.cncf.io/blog/example, 2026-05-03 확인.
- 불확실성: 특정 프로젝트 채택 여부와 성능 영향은 원문만으로 단정하지 않습니다.
"""
    errors = linter.lint_text(md)
    assert any("thin confirmed fact" in err for err in errors)



def test_daily_hot_issues_linter_rejects_category_template_without_source_content_summary():
    md = """# 오늘의 핫이슈

## 주요 이슈

### 경제 성장률 전망 조정
- 출처 성격: 보도.
- 확인된 사실: 경제 분야에서는 대표 요약의 구체 변화가 확인되어 관련 정책·시장·사회 파급을 볼 필요가 있습니다.
- 왜 중요한가: 경제 분야에서는 대표 요약의 구체 변화가 확인되어 후속 공지 여부를 원문 기준으로 분리해 볼 필요가 있습니다.
- 오늘 할 일: 원문에서 발표 주체, 날짜, 핵심 수치, 후속 조치를 확인합니다.
- 근거: https://example.com/economy, 2026-05-03 확인.
- 불확실성: 세부 영향은 단정하지 않습니다.
"""
    errors = linter.lint_text(md)
    joined = "\n".join(errors)
    assert "source-content summary" in joined or "category/meta filler" in joined


def test_daily_hot_issues_linter_accepts_source_grounded_article_summary():
    md = """# 오늘의 핫이슈

## 주요 이슈

### 한국은행, 성장률 전망 하향과 내수 부진 리스크 설명
- 출처 성격: 보도.
- 확인된 사실: 본 기사는 한국은행이 올해 경제 성장률 전망을 낮추고 반도체 수출 회복에도 내수 부진이 성장률을 제약한다고 설명했다는 내용을 다뤘다.
- 왜 중요한가: 성장률 전망 하향은 정책당국이 수출 회복만으로 경기 반등을 확신하지 않는다는 뜻이라 예산·R&D·기업 투자 판단의 전제치를 낮춰 잡아야 합니다.
- 오늘 할 일: Example Economy 원문에서 성장률 조정 폭, 한국은행의 내수 부진 근거, 다음 전망 수정 시점을 확인합니다.
- 근거: https://example.com/economy, 2026-05-03 확인.
- 불확실성: 기사 요약이므로 실제 수치와 발언 맥락은 원문 표와 인용문으로 재확인해야 합니다.
"""
    assert linter.lint_text(md) == []

def test_daily_hot_issues_linter_ignores_reader_dashboard_h3_outside_issue_sections():
    md = """# 오늘의 핫이슈

## 한눈에 보기

### 독자 대시보드

- 오늘 실제로 읽을 카드: 1개 (주요 이슈 1개, 원문 확인 뉴스 0개, 신청 가능 공고 0개).
- 보류된 뉴스 카테고리: 0개 — 없음.
- 즉시 확인 액션: 1개 — 주요 이슈 원문 확인 1건.

## 주요 이슈

### OpenAI, 에이전트 권한 정책 공개
- 출처 성격: 공식 블로그.
- 확인된 사실: OpenAI가 에이전트 권한 관리와 검토 흐름을 공개했다.
- 왜 중요한가: 에이전트가 외부 도구를 실행할 때 승인·권한·감사 로그 경계가 제품 안전성의 핵심 조건이 되므로 로컬 자동화 권한 모델 점검에도 직접 참고된다.
- 오늘 할 일: 공식 원문에서 권한 검토 절차, 사용자 승인 조건, 감사 로그 제공 범위를 확인한다.
- 근거: https://example.com/openai-policy, 2026-04-30 확인.
- 불확실성: 실제 제품별 적용 범위는 추가 확인이 필요하다.
"""
    assert linter.lint_text(md) == []


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


def test_daily_hot_issues_linter_stops_issue_card_at_next_h2_section():
    md = """# 오늘의 핫이슈

## 주요 이슈

### OpenAI, 에이전트 권한 정책 공개
- 출처 성격: 공식 블로그.
- 확인된 사실: OpenAI가 에이전트 권한 관리와 검토 흐름을 공개했다.
- 왜 중요한가: 에이전트가 외부 도구를 실행할 때 승인·권한·감사 로그 경계가 제품 안전성의 핵심 조건이 되므로 로컬 자동화 권한 모델 점검에도 직접 참고된다.
- 오늘 할 일: 공식 원문에서 권한 검토 절차, 사용자 승인 조건, 감사 로그 제공 범위를 확인한다.
- 근거: https://example.com/openai-policy, 2026-04-30 확인.
- 불확실성: 실제 제품별 적용 범위는 추가 확인이 필요하다.

## 개인 기회/공고 검토

- **IRIS AI 기반 대학 과학기술 혁신사업 후보** — 상태: **검토 필요**.
  - 공고 URL: https://www.iris.go.kr/
  - 보류 사유: 상세 공식 URL, 접수기간/마감, 지원대상/자격, 지원내용
"""
    assert linter.lint_text(md) == []


def test_daily_hot_issues_linter_does_not_apply_opportunity_contract_to_news_category_briefs():
    md = """# 오늘의 핫이슈

## 주요 이슈

### OpenAI, 에이전트 권한 정책 공개
- 출처 성격: 공식 블로그.
- 확인된 사실: OpenAI가 에이전트 권한 관리와 검토 흐름을 공개했다.
- 왜 중요한가: 에이전트가 외부 도구를 실행할 때 승인·권한·감사 로그 경계가 제품 안전성의 핵심 조건이 되므로 로컬 자동화 권한 모델 점검에도 직접 참고된다.
- 오늘 할 일: 공식 원문에서 권한 검토 절차, 사용자 승인 조건, 감사 로그 제공 범위를 확인한다.
- 근거: https://example.com/openai-policy, 2026-04-30 확인.
- 불확실성: 실제 제품별 적용 범위는 추가 확인이 필요하다.

## 뉴스 카테고리별 브리핑

### 정치
- 출처 성격: 보도.
- 확인된 사실: 보궐선거 접수 마감 관련 보도가 수집됐습니다.
- 왜 중요한가: 정치 분야 흐름을 원문 기준으로 확인하기 위한 브리핑입니다.
- 오늘 할 일: Naver News 원문을 열어 발표 주체, 날짜, 후속 조치를 확인합니다.
- 근거: naver-news / https://n.news.naver.com/example / 2026-04-30
- 불확실성: 제목만으로 사실관계나 영향 범위를 단정하지 않습니다.
"""
    assert linter.lint_text(md) == []
