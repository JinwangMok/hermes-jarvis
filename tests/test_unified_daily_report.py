from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from jinwang_jarvis.cli import build_parser, main
from jinwang_jarvis.unified_daily_report import (
    DeliveryGateError,
    OpportunityCandidate,
    compose_unified_daily_report,
    validate_unified_daily_report,
    write_unified_daily_report,
)


def _news_items() -> list[dict[str, object]]:
    return [
        {
            "title": "경제 성장률 전망 조정",
            "url": "https://example.com/economy",
            "provider": "google-news",
            "source": "Example Economy",
            "category": "economy",
            "scope": "domestic",
            "summary": "한국은행이 올해 경제 성장률 전망을 낮추고 반도체 수출 회복에도 내수 부진이 성장률을 제약한다고 설명했다.",
            "body_text": "한국은행이 올해 경제 성장률 전망을 낮추고 반도체 수출 회복에도 내수 부진이 성장률을 제약한다고 설명했다. 기사에서는 수출과 내수의 괴리가 커지는 상황에서 정책당국의 경기 판단이 보수적으로 바뀌었다는 점을 다뤘다.",
            "published_at": "2026-04-30",
            "content_hash": "economyhash1234",
        },
        {
            "title": "사회 안전망 논의 확대",
            "url": "https://example.com/society",
            "provider": "naver-news",
            "source": "Example Society",
            "category": "society",
            "scope": "domestic",
            "summary": "사회 정책 논의가 확대됐다.",
            "published_at": "2026-04-30",
            "content_hash": "societyhash1234",
        },
        {
            "title": "문화 행사 지원 발표",
            "url": "https://example.com/culture",
            "provider": "naver-news",
            "source": "Example Culture",
            "category": "culture",
            "scope": "domestic",
            "summary": "문화 행사 지원 계획이 발표됐다.",
            "published_at": "2026-04-30",
            "content_hash": "culturehash1234",
        },
    ]


def _valid_hot_issue_markdown() -> str:
    return """# 오늘의 핫이슈

## 주요 이슈

### OpenAI, 새 모델 도구 정책 공개
- 출처 성격: 공식 블로그.
- 확인된 사실: OpenAI가 새 도구 정책을 공개했다.
- 왜 중요한가: 새 도구 정책은 에이전트가 외부 API와 파일·브라우저 도구를 호출할 때 권한 범위와 승인 지점을 어디에 둘지 정하는 기준이 되어, 자동화 제품의 안전 설계 검토 항목을 바꾼다.
- 오늘 할 일: 공식 원문에서 적용 대상 API, 권한 승인 방식, 기존 도구 호출 정책과 달라진 문구를 비교해 기록한다.
- 근거: https://example.com/openai, 2026-04-30 확인.
- 불확실성: 적용 범위는 추가 확인이 필요하다.
"""


def _markdown_visible_text(markdown: str) -> str:
    return re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", markdown)


def test_compose_unified_daily_report_has_required_sections_and_categories() -> None:
    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=_news_items(),
        opportunity_candidates=[],
    )

    for heading in ["한눈에 보기", "오늘의 체크리스트", "주요 이슈", "개인 기회/공고 검토", "뉴스 카테고리별 브리핑", "근거 커버리지"]:
        assert f"## {heading}" in report.markdown
    assert "오늘 검증된 개인 기회/공고 후보는 없습니다" in report.markdown
    for category in ["정치", "경제", "사회", "문화", "국제", "기술", "예능"]:
        assert f"### {category}" in report.markdown
    assert "Appendix" not in report.markdown
    assert "####" not in report.markdown
    assert validate_unified_daily_report(report.markdown) == []


def test_compose_unified_daily_report_holds_news_when_body_is_only_title_plus_provider_boilerplate() -> None:
    boilerplate_news = [
        {
            "title": "김태년, 국회의장 출마선언",
            "url": "https://n.news.naver.com/mnews/article/009/0000000000",
            "provider": "naver-news",
            "source": "Naver News",
            "category": "politics",
            "summary": "김태년, 국회의장 출마선언",
            "body_text": "김태년, 국회의장 출마선언 이동 통신망을 이용하여 음성을 재생하면 별도의 데이터 통화료가 부과될 수 있습니다. Copyright ⓒ 매일경제. 무단 전재, 재배포 및 AI학습 이용 금지. 언론사는 개별 기사를 2개 이상 섹션으로 중복 분류할 수 있습니다. 이 기사를 본 이용자들이 함께 많이 본 기사 등을 자동 추천합니다",
            "content_hash": "boilerplatehash",
        }
    ]

    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=boilerplate_news,
        opportunity_candidates=[],
    )

    assert "언론사는 개별 기사를" not in report.markdown
    assert "이동 통신망을 이용" not in report.markdown
    assert "정치 분야에서 오늘 보고에 올릴 만큼 원문 내용이 확인된 항목이 없습니다" in report.markdown


def test_compose_unified_daily_report_allows_no_promoted_main_issue_when_news_has_reader_value() -> None:
    thin_hot_issue = """## 🔥 핫이슈 업데이트

### 1. Thin internal candidate
**분류:** agent-watch · **열기:** low
**관심도:** 중요도 **0.620** · 모멘텀 **0.000**
**내용 요약:** 제목만 있는 후보
**출처:** https://example.com/thin
"""

    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=thin_hot_issue,
        news_items=_news_items(),
        opportunity_candidates=[],
    )

    assert "승격된 주요 이슈 없음" in report.markdown
    assert "분류:" not in report.markdown
    assert "모멘텀" not in report.markdown
    assert validate_unified_daily_report(report.markdown) == []


def test_compose_unified_daily_report_hides_visible_raw_urls_in_body_text() -> None:
    opportunity = OpportunityCandidate(
        title="AI 연구지원 직접 공고",
        official_url="https://example.com/opportunity",
        deadline_window="2026-05-01~2026-05-31",
        eligibility="대학 연구실",
        support_contents="클라우드 크레딧 지원",
        evidence_note="상세 공고 https://example.com/opportunity 확인",
    )

    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=_news_items(),
        opportunity_candidates=[opportunity],
    )

    visible_text = _markdown_visible_text(report.markdown)
    assert "https://" not in visible_text
    assert "http://" not in visible_text
    assert "- 근거: [원문 링크](https://example.com/openai), 2026-04-30 확인." in report.markdown
    assert "공고 URL: [공식 공고 링크](https://example.com/opportunity)" in report.markdown
    assert "판단 근거: 상세 공고 [근거 링크](https://example.com/opportunity) 확인" in report.markdown
    assert "- 근거: google-news / [Example Economy](https://example.com/economy)" in report.markdown
    assert "- 근거: [뉴스 검색 링크](https://news.google.com/), 2026-04-30 확인." in report.markdown
    assert validate_unified_daily_report(report.markdown) == []


def test_compose_unified_daily_report_news_briefs_do_not_use_generic_why_template() -> None:
    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=_news_items(),
        opportunity_candidates=[],
    )

    assert "분야의 정책·시장·사회 흐름을 원문 기준으로 확인하기 위한 독자용 브리핑" not in report.markdown
    assert "한국은행 발표: 올해 경제 성장률 전망을 낮추고" in report.markdown
    assert "수출과 내수의 괴리" in report.markdown
    assert "경제 분야에서는" not in report.markdown
    assert "항목이 수집" not in report.markdown


def test_compose_unified_daily_report_empty_categories_do_not_expose_pipeline_jargon() -> None:
    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=[_news_items()[0]],
        opportunity_candidates=[],
    )

    assert "fetch" not in report.markdown.lower()
    assert "selector" not in report.markdown.lower()
    assert "크롤러" not in report.markdown
    assert "수집·추출 실패" not in report.markdown
    assert "오늘 보고에 올릴 만큼 원문 내용이 확인된 항목이 없습니다" in report.markdown


def test_compose_unified_daily_report_adds_reader_dashboard_with_readable_held_and_action_counts() -> None:
    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=[_news_items()[0]],
        opportunity_candidates=[],
    )

    dashboard = report.markdown.split("## 한눈에 보기", 1)[1].split("## 주요 이슈", 1)[0]
    assert "오늘 집중할 것" in dashboard
    assert "OpenAI, 새 모델 도구 정책 공개" in dashboard
    assert "오늘 실제로 읽을 카드" not in dashboard
    assert "보류된 뉴스 카테고리" not in dashboard
    assert "즉시 확인 액션" not in dashboard


def test_compose_unified_daily_report_promotes_domain_hot_issue_candidates_without_required_field_template() -> None:
    hot = """## 🔥 핫이슈 업데이트

### 1. https://x.com/i/broadcasts/1nKOLEVedLrGR Our podcast is live! There are Ouroboros philosophy, how to use it, and real demo with claude, codex, hermes And I aim that Agent OS will be release at Ouroboros 1.0.0
**분류:** omocon-agentic-ai · **열기:** low
**관심도:** 중요도 **0.620** · 모멘텀 **0.000**
**내용 요약:** <p>Our podcast is live! There are Ouroboros philosophy, how to use it, and real demo with claude, codex, hermes. And I aim that Agent OS will be release at Ouroboros 1.0.0</p>
**출처:** https://x.com/JqOnly/status/2050393912049881521

### 2. Agent OS
Ouroboros has been evolving into an Agent OS
https://github.com/Q00/ouroboros
**분류:** omocon-agentic-ai · **열기:** low
**내용 요약:** <p>Agent OS. Ouroboros has been evolving into an Agent OS. https://github.com/Q00/ouroboros</p>
**출처:** https://x.com/JqOnly/status/2050661382488801301
"""

    report = compose_unified_daily_report(
        report_date="2026-05-03",
        hot_issue_markdown=hot,
        news_items=_news_items(),
        opportunity_candidates=[],
    )

    main = report.markdown.split("## 주요 이슈", 1)[1].split("## 뉴스 카테고리별 브리핑", 1)[0]
    assert "승격된 주요 이슈 없음" not in main
    assert "Ouroboros" in main
    assert "Agent OS" in main
    assert "claude, codex, hermes" in main
    assert "분류:" not in main
    assert "모멘텀" not in main


def test_compose_unified_daily_report_drops_low_level_tool_maintenance_commits() -> None:
    hot = """## 🔥 핫이슈 업데이트

### 1. This release lands two major milestones of the Agent OS RFC.

1. I/O journal Layer
Every LLM call and tool dispatch is now wrapped in a structured, privacy-aware journal.

2. AgentProcess cooperative lifecycle
Ouroboros can execute other harnesses for specific contracts.
**내용 요약:** This release lands two major milestones of the Agent OS RFC.
**출처:** https://github.com/Q00/ouroboros/releases/tag/v0.32.0

### 2. Fix HUD statusLine cold-start flicker (#2844)
**내용 요약:** Fix HUD statusLine cold-start flicker and cache statusLine renderer output for one CLI tool.
**출처:** https://github.com/Yeachan-Heo/oh-my-claudecode/commit/45d1855fc7ba140615f6d75889496aa1e8a8e656

### 3. Merge pull request #2914 from Yeachan-Heo/issue-2913-prebuild-warning
**내용 요약:** docs: explain prebuild-install warning.
**출처:** https://github.com/Yeachan-Heo/oh-my-claudecode/commit/836699c9392da5c49407e2db36d9b556819b8e9d

### 4. docs(release): add v4.13.6 release notes
**내용 요약:** docs(release): add v4.13.6 release notes Covers 14 net-user-facing PRs since v4.13.5.
**출처:** https://github.com/Yeachan-Heo/oh-my-claudecode/commit/23b01a
"""

    report = compose_unified_daily_report(
        report_date="2026-05-04",
        hot_issue_markdown=hot,
        news_items=_news_items(),
        opportunity_candidates=[],
    )

    main = report.markdown.split("## 주요 이슈", 1)[1].split("## 뉴스 카테고리별 브리핑", 1)[0]
    assert "Agent OS" in main
    assert "I/O journal" in main
    assert "AgentProcess" in main
    assert "Fix HUD statusLine" not in main
    assert "Merge pull request" not in main
    assert "docs(release)" not in main


def test_compose_unified_daily_report_news_brief_uses_article_content_not_category_template() -> None:
    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=_news_items(),
        opportunity_candidates=[],
    )

    economy_section = report.markdown.split("### 경제", 1)[1].split("### 사회", 1)[0]
    assert "- 확인된 사실: 한국은행 발표: 올해 경제 성장률 전망을 낮추고" in economy_section
    assert "내수 부진이 성장률을 제약" in economy_section
    assert "수출과 내수의 괴리" in economy_section
    assert "- 왜 중요한가: 성장률 전망 하향은" in economy_section
    assert "- 오늘 할 일: Example Economy 원문에서 성장률 조정 폭" in economy_section
    assert "정책·시장·사회 흐름" not in economy_section


def test_compose_unified_daily_report_extracts_actor_numbers_timing_and_followup_from_body() -> None:
    news_items = [
        {
            "title": "CNCF, Kubernetes 1.34 릴리스 후보 공개",
            "url": "https://example.com/k8s-134",
            "provider": "tech-news",
            "source": "Example Tech",
            "category": "technology",
            "body_text": (
                "서론 문장은 쿠버네티스 생태계가 빠르게 바뀐다는 일반 설명만 담고 있다. "
                "CNCF와 Kubernetes 릴리스팀은 2026년 5월 1일 Kubernetes 1.34 첫 번째 릴리스 후보를 공개하고 "
                "관리자에게 kube-apiserver 보안 기본값 변경과 20개 API 제거 예정 항목을 점검하라고 안내했다. "
                "릴리스팀은 운영자가 6월 정식 릴리스 전까지 스테이징 클러스터에서 업그레이드 리허설을 완료해야 한다고 밝혔다."
            ),
            "published_at": "2026-05-01",
            "content_hash": "techhash123456",
        }
    ]

    report = compose_unified_daily_report(
        report_date="2026-05-02",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=news_items,
        opportunity_candidates=[],
    )

    tech_section = report.markdown.split("### 기술", 1)[1].split("### 예능", 1)[0]
    assert "일반 설명만 담고 있다" not in tech_section
    assert "CNCF와 Kubernetes 릴리스팀 발표" in tech_section
    assert "2026년 5월 1일" in tech_section
    assert "Kubernetes 1.34" in tech_section
    assert "20개 API 제거 예정" in tech_section
    assert "6월 정식 릴리스 전" in tech_section
    assert "스테이징 클러스터" in tech_section


def test_compose_unified_daily_report_enriches_title_only_news_from_url_before_briefing() -> None:
    def fake_fetch(url: str) -> str:
        assert url == "https://example.com/title-only"
        return """<html><head><link rel=\"canonical\" href=\"https://example.com/title-only\"></head><body><article>
        <p>한국은행은 올해 경제 성장률 전망을 낮추면서 고금리 장기화와 민간소비 둔화를 핵심 근거로 제시했다.</p>
        <p>기사에서는 반도체 수출 회복에도 내수 부진이 이어지면 하반기 경기 반등 폭이 제한될 수 있다고 설명했다.</p>
        </article></body></html>"""

    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=[{
            "title": "제목만 있는 속보",
            "url": "https://example.com/title-only",
            "provider": "naver-news",
            "source": "Example News",
            "category": "economy",
            "scope": "domestic",
            "published_at": "2026-04-30",
            "content_hash": "titleonlyhash",
        }],
        opportunity_candidates=[],
        news_body_fetcher=fake_fetch,
    )

    economy_section = report.markdown.split("### 경제", 1)[1].split("### 사회", 1)[0]
    assert "한국은행 발표: 올해 경제 성장률 전망을 낮추면서" in economy_section
    assert "검증 가능한 원문 본문/요약 입력이 없습니다" not in economy_section


def test_compose_unified_daily_report_strips_html_and_raw_urls_from_fallback_hot_issue_summary() -> None:
    hot = """# 오늘의 핫이슈

## 주요 이슈

### shooting podcast with <a href=\"https://nitter.net/JqOnly\">@JqOnly</a>
<p>recording with <a href=\"https://nitter.net/JqOnly\" title=\"JQ Lee\">@JqOnly</a></p>
정량 신호: 관측 총 1건
<img src=\"https://nitter.net/pic/media.jpg\">
"""
    with pytest.raises(ValueError, match="main issue section"):
        compose_unified_daily_report(report_date="2026-04-30", hot_issue_markdown=hot, news_items=[], opportunity_candidates=[])


def test_compose_unified_daily_report_keeps_structured_reader_facing_issue_cards() -> None:
    hot = _valid_hot_issue_markdown()
    report = compose_unified_daily_report(report_date="2026-04-30", hot_issue_markdown=hot, news_items=[], opportunity_candidates=[])
    main_issue = report.markdown.split("## 주요 이슈", 1)[1].split("## 개인 기회/공고 검토", 1)[0]

    assert "### OpenAI, 새 모델 도구 정책 공개" in main_issue
    assert "- 출처 성격: 공식 블로그." in main_issue


def test_opportunity_candidates_are_gated_inside_unified_report_only() -> None:
    unqualified = OpportunityCandidate(
        title="IRIS AI 기반 대학 과학기술 혁신사업 후보",
        official_url="https://www.iris.go.kr/",
        deadline_window="",
        eligibility="",
        support_contents="",
        evidence_note="공식 상세 공고 전 검토 후보",
    )

    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=[],
        opportunity_candidates=[unqualified],
    )

    section = report.markdown.split("## 개인 기회/공고 검토", 1)[1].split("## 뉴스 카테고리별 브리핑", 1)[0]
    assert "IRIS AI 기반 대학 과학기술 혁신사업 후보" in section
    assert "검토 필요" in section or "보류" in section
    assert "신청 가능" not in section
    assert "# Personal Opportunity Radar" not in report.markdown


def test_validation_rejects_missing_required_sections() -> None:
    errors = validate_unified_daily_report("# 오늘의 핫이슈\n\n## 주요 이슈\n본문\n")

    assert any("한눈에 보기" in error for error in errors)
    assert any("뉴스 카테고리별 브리핑" in error for error in errors)


def test_write_unified_daily_report_writes_single_markdown_and_pdf_path(tmp_path: Path) -> None:
    result = write_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=[],
        opportunity_candidates=[],
        wiki_root=tmp_path / "wiki",
        workspace_root=tmp_path,
    )

    markdown_path = result["markdown_path"]
    pdf_path = result["pdf_path"]
    assert isinstance(markdown_path, str)
    assert isinstance(pdf_path, str)
    assert markdown_path == str(tmp_path / "wiki" / "reports" / "hot-issues" / "daily" / "2026-04-30.md")
    assert pdf_path == str(tmp_path / "data" / "reports" / "daily-hot-issues-2026-04-30.pdf")
    assert Path(markdown_path).exists()
    markdown = Path(markdown_path).read_text(encoding="utf-8")
    assert "## 주요 이슈" in markdown
    assert "## 개인 기회/공고 검토" in markdown
    assert "오늘 검증된 개인 기회/공고 후보는 없습니다" in markdown
    assert "신청 가능한 공고 없음" not in markdown


def test_cli_exposes_generate_unified_daily_report_command_with_gate_enabled_by_default() -> None:
    parser = build_parser()

    args = parser.parse_args([
        "generate-unified-daily-report",
        "--config",
        "config/pipeline.local.yaml",
        "--date",
        "2026-04-30",
    ])

    assert args.command == "generate-unified-daily-report"
    assert args.date == "2026-04-30"
    assert args.delivery_gate is True


def test_cli_generate_unified_daily_report_has_explicit_gate_bypass_for_local_debug_only() -> None:
    parser = build_parser()

    args = parser.parse_args([
        "generate-unified-daily-report",
        "--config",
        "config/pipeline.local.yaml",
        "--date",
        "2026-04-30",
        "--skip-delivery-gate",
    ])

    assert args.delivery_gate is False


def test_write_unified_daily_report_runs_hard_gate_by_default(tmp_path: Path, monkeypatch) -> None:
    gate_calls = []

    class FakeGateResult:
        ok = True
        failed_stage = None
        errors = []
        pdfinfo = "Pages: 1\n"

        def __init__(self, markdown: Path, pdf: Path) -> None:
            self.markdown = markdown
            self.pdf = pdf
            self.html = pdf.with_suffix(".html")
            self.text = pdf.with_suffix(".txt")

    def fake_gate(markdown: Path, *, pdf: Path):
        gate_calls.append((markdown, pdf))
        pdf.write_bytes(b"%PDF-1.7\n")
        return FakeGateResult(markdown, pdf)

    monkeypatch.setattr("jinwang_jarvis.unified_daily_report.run_daily_hot_issues_delivery_gate", fake_gate)

    result = write_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown=_valid_hot_issue_markdown(),
        news_items=_news_items(),
        opportunity_candidates=[],
        wiki_root=tmp_path / "wiki",
        workspace_root=tmp_path,
    )

    markdown_path = tmp_path / "wiki" / "reports" / "hot-issues" / "daily" / "2026-04-30.md"
    pdf_path = tmp_path / "data" / "reports" / "daily-hot-issues-2026-04-30.pdf"
    assert gate_calls
    assert gate_calls[0][0] != markdown_path
    assert gate_calls[0][1] != pdf_path
    assert markdown_path.exists()
    assert pdf_path.exists()
    assert result["delivery_gate"]["ok"] is True
    assert result["delivery_gate"]["markdown_path"] == str(markdown_path)
    assert result["delivery_gate"]["pdf_path"] == str(pdf_path)


def test_write_unified_daily_report_raises_when_delivery_gate_fails(tmp_path: Path, monkeypatch) -> None:
    class FakeGateResult:
        ok = False
        failed_stage = "first-reader-qa"
        errors = ["reader-facing text missing required cue: 근거"]
        pdfinfo = ""
        html = None
        text = None

        def __init__(self, markdown: Path, pdf: Path) -> None:
            self.markdown = markdown
            self.pdf = pdf

    def fake_gate(markdown: Path, *, pdf: Path):
        return FakeGateResult(markdown, pdf)

    monkeypatch.setattr("jinwang_jarvis.unified_daily_report.run_daily_hot_issues_delivery_gate", fake_gate)

    with pytest.raises(DeliveryGateError) as excinfo:
        write_unified_daily_report(
            report_date="2026-04-30",
            hot_issue_markdown=_valid_hot_issue_markdown(),
            news_items=_news_items(),
            opportunity_candidates=[],
            wiki_root=tmp_path / "wiki",
            workspace_root=tmp_path,
            delivery_gate=True,
        )

    assert excinfo.value.result["ok"] is False
    assert excinfo.value.result["failed_stage"] == "first-reader-qa"
    assert not (tmp_path / "wiki" / "reports" / "hot-issues" / "daily" / "2026-04-30.md").exists()
    assert not (tmp_path / "data" / "reports" / "daily-hot-issues-2026-04-30.pdf").exists()


def test_cli_generate_unified_daily_report_smoke(tmp_path: Path, capsys) -> None:
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        f"""
workspace_root: {tmp_path.as_posix()}
wiki_root: {(tmp_path / 'wiki').as_posix()}
accounts: []
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 100
  sent_folder_overrides: {{}}
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
  max_results: 5
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord-origin
reproducibility:
  project_name: jinwang-jarvis
""".strip(),
        encoding="utf-8",
    )
    hot_issue = tmp_path / "hot.md"
    hot_issue.write_text(_valid_hot_issue_markdown(), encoding="utf-8")
    news_json = tmp_path / "news.json"
    news_json.write_text(json.dumps({"items": _news_items()}, ensure_ascii=False), encoding="utf-8")

    exit_code = main([
        "generate-unified-daily-report",
        "--config",
        str(config),
        "--date",
        "2026-04-30",
        "--hot-issue",
        str(hot_issue),
        "--news-json",
        str(news_json),
        "--skip-delivery-gate",
    ])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert Path(output["markdown_path"]).exists()
    assert output["pdf_path"].endswith("data/reports/daily-hot-issues-2026-04-30.pdf")


def test_cli_generate_unified_daily_report_with_delivery_gate(tmp_path: Path, capsys, monkeypatch) -> None:
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        f"""
workspace_root: {tmp_path.as_posix()}
wiki_root: {(tmp_path / 'wiki').as_posix()}
accounts: []
mail:
  snapshot_dir: data/snapshots/mail
  page_size: 100
  sent_folder_overrides: {{}}
calendar:
  snapshot_dir: data/snapshots/calendar
  calendar_id: primary
  max_results: 5
state:
  database: state/personal_intel.db
  checkpoints: state/checkpoints.json
hermes:
  integration_mode: boundary-cli
  deliver_channel: discord-origin
reproducibility:
  project_name: jinwang-jarvis
""".strip(),
        encoding="utf-8",
    )
    hot_issue = tmp_path / "hot.md"
    hot_issue.write_text(_valid_hot_issue_markdown(), encoding="utf-8")
    news_json = tmp_path / "news.json"
    news_json.write_text(json.dumps({"items": _news_items()}, ensure_ascii=False), encoding="utf-8")

    class FakeGateResult:
        ok = True
        failed_stage = None
        errors = []
        pdfinfo = "Pages: 1\n"

        def __init__(self, markdown: Path, pdf: Path) -> None:
            self.markdown = markdown
            self.pdf = pdf
            self.html = pdf.with_suffix(".html")
            self.text = pdf.with_suffix(".txt")

    def fake_gate(markdown: Path, *, pdf: Path):
        pdf.write_bytes(b"%PDF-1.7\n")
        return FakeGateResult(markdown, pdf)

    monkeypatch.setattr("jinwang_jarvis.unified_daily_report.run_daily_hot_issues_delivery_gate", fake_gate)

    exit_code = main([
        "generate-unified-daily-report",
        "--config",
        str(config),
        "--date",
        "2026-04-30",
        "--hot-issue",
        str(hot_issue),
        "--news-json",
        str(news_json),
        "--delivery-gate",
    ])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["delivery_gate"]["ok"] is True
    assert output["delivery_gate"]["pdf_path"] == output["pdf_path"]
