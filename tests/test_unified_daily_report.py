from __future__ import annotations

import json
import re
from pathlib import Path

from jinwang_jarvis.cli import build_parser, main
from jinwang_jarvis.unified_daily_report import (
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
            "summary": "한국 경제 성장률 전망이 조정됐다.",
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


def _markdown_visible_text(markdown: str) -> str:
    return re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", markdown)


def test_compose_unified_daily_report_has_required_sections_and_categories() -> None:
    report = compose_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown="# 오늘의 핫이슈\n\n## 주요 이슈\n\n### OpenAI, 새 모델 도구 정책 공개\n- 출처 성격: 공식 블로그.\n- 확인된 사실: OpenAI가 새 도구 정책을 공개했다.\n- 왜 중요한가: 에이전트 권한 설계에 영향을 준다.\n- 오늘 할 일: 공식 원문을 확인한다.\n- 근거: https://example.com/openai, 2026-04-30 확인.\n- 불확실성: 적용 범위는 추가 확인이 필요하다.\n",
        news_items=_news_items(),
        opportunity_candidates=[],
    )

    for heading in ["한눈에 보기", "오늘의 체크리스트", "주요 이슈", "개인 기회/공고 검토", "뉴스 카테고리별 브리핑", "근거 커버리지"]:
        assert f"## {heading}" in report.markdown
    for category in ["정치", "경제", "사회", "문화", "국제", "기술", "예능"]:
        assert f"### {category}" in report.markdown
    assert "Appendix" not in report.markdown
    assert "####" not in report.markdown
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
        hot_issue_markdown="# 오늘의 핫이슈\n\n## 주요 이슈\n\n### OpenAI, 새 모델 도구 정책 공개\n- 출처 성격: 공식 블로그.\n- 확인된 사실: OpenAI가 새 도구 정책을 공개했다.\n- 왜 중요한가: 에이전트 권한 설계에 영향을 준다.\n- 오늘 할 일: 공식 원문을 확인한다.\n- 근거: https://example.com/openai, 2026-04-30 확인.\n- 불확실성: 적용 범위는 추가 확인이 필요하다.\n",
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
        hot_issue_markdown="",
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

    assert any("개인 기회/공고 검토" in error for error in errors)
    assert any("뉴스 카테고리별 브리핑" in error for error in errors)


def test_write_unified_daily_report_writes_single_markdown_and_pdf_path(tmp_path: Path) -> None:
    result = write_unified_daily_report(
        report_date="2026-04-30",
        hot_issue_markdown="",
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
    assert "개인 기회/공고 검토" in Path(markdown_path).read_text(encoding="utf-8")


def test_cli_exposes_generate_unified_daily_report_command() -> None:
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
    news_json = tmp_path / "news.json"
    news_json.write_text(json.dumps({"items": _news_items()}, ensure_ascii=False), encoding="utf-8")

    exit_code = main([
        "generate-unified-daily-report",
        "--config",
        str(config),
        "--date",
        "2026-04-30",
        "--news-json",
        str(news_json),
    ])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert Path(output["markdown_path"]).exists()
    assert output["pdf_path"].endswith("data/reports/daily-hot-issues-2026-04-30.pdf")
