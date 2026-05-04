import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gate_daily_hot_issues_delivery.py"

spec = importlib.util.spec_from_file_location("gate_daily_hot_issues_delivery", SCRIPT)
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)


def _good_md() -> str:
    return """# 오늘의 핫이슈 리포트 — 2026-05-04

- 보고 기준 시각: 2026-05-04 09:00 KST

## 주요 이슈

### OpenAI, 에이전트 권한 정책 공개
- 출처 성격: 공식 블로그.
- 확인된 사실: OpenAI가 에이전트 권한 관리와 사용자 승인 흐름을 공식 블로그에서 공개했다.
- 왜 중요한가: 에이전트가 외부 도구를 실행할 때 승인·권한·감사 로그 경계가 제품 안전성의 핵심 조건이 되므로 로컬 자동화 권한 모델 점검에도 직접 참고된다.
- 오늘 할 일: 공식 원문에서 권한 검토 절차, 사용자 승인 조건, 감사 로그 제공 범위를 확인한다.
- 근거: https://example.com/openai-policy, 2026-05-04 확인.
- 불확실성: 실제 제품별 적용 범위는 추가 확인이 필요하다.
"""


class FakeCompleted:
    def __init__(self, args, returncode=0, stdout="", stderr=""):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_delivery_gate_runs_lint_render_pdfinfo_pdftotext_and_reader_qa(tmp_path: Path, monkeypatch):
    md = tmp_path / "daily.md"
    md.write_text(_good_md(), encoding="utf-8")
    calls = []

    def fake_render(markdown: Path, *, pdf: Path, html: Path | None = None) -> None:
        calls.append(("render", markdown, pdf, html))
        pdf.write_bytes(b"%PDF-1.7\n% fake\n")
        if html:
            html.write_text("<html>ok</html>", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        calls.append(tuple(cmd))
        if cmd[0] == "pdfinfo":
            return FakeCompleted(cmd, stdout="Title: Daily Hot Issues\nPages: 2\n")
        if cmd[0] == "pdftotext":
            assert "-layout" in cmd
            Path(cmd[-1]).write_text(
                "오늘의 핫이슈 리포트\nOpenAI, 에이전트 권한 정책 공개\n"
                "출처 성격 공식 블로그\n확인된 사실 OpenAI가 권한 관리와 사용자 승인 흐름을 공개\n"
                "왜 중요한가 권한 경계와 감사 로그 점검에 직접 참고됨\n오늘 할 일 공식 원문 확인\n근거 원문 링크\n불확실성 제품별 적용 범위 추가 확인 및 도입 전 권한 정책 비교 필요, 운영 환경별 승인 흐름 재점검 필요\n",
                encoding="utf-8",
            )
            return FakeCompleted(cmd)
        raise AssertionError(cmd)

    monkeypatch.setattr(gate, "render_pdf", fake_render)
    result = gate.run_delivery_gate(md, pdf=tmp_path / "daily.pdf", html=tmp_path / "daily.html", runner=fake_run)

    assert result.ok is True
    assert result.pdf == tmp_path / "daily.pdf"
    assert [c[0] for c in calls] == ["render", "pdfinfo", "pdftotext"]


def test_delivery_gate_hard_fails_before_render_when_content_lint_fails(tmp_path: Path, monkeypatch):
    md = tmp_path / "bad.md"
    md.write_text("# 오늘의 핫이슈\n\n## 주요 이슈\n\n### high-heat 신호\n- 내용: 후보\n", encoding="utf-8")
    rendered = False

    def fake_render(*args, **kwargs):
        nonlocal rendered
        rendered = True

    monkeypatch.setattr(gate, "render_pdf", fake_render)
    result = gate.run_delivery_gate(md, pdf=tmp_path / "bad.pdf")

    assert result.ok is False
    assert rendered is False
    assert result.failed_stage == "content-lint"
    assert any("daily hot-issues content lint failed" in e for e in result.errors)


def test_delivery_gate_hard_fails_on_pdfinfo_error(tmp_path: Path, monkeypatch):
    md = tmp_path / "daily.md"
    md.write_text(_good_md(), encoding="utf-8")

    def fake_render(markdown: Path, *, pdf: Path, html: Path | None = None) -> None:
        pdf.write_bytes(b"%PDF-1.7\n")

    def fake_run(cmd, **kwargs):
        return FakeCompleted(cmd, returncode=1, stderr="Syntax Error: not a PDF")

    monkeypatch.setattr(gate, "render_pdf", fake_render)
    result = gate.run_delivery_gate(md, pdf=tmp_path / "daily.pdf", runner=fake_run)

    assert result.ok is False
    assert result.failed_stage == "pdfinfo"
    assert any("not a PDF" in e for e in result.errors)


def test_delivery_gate_hard_fails_on_first_reader_qa_after_pdftotext(tmp_path: Path, monkeypatch):
    md = tmp_path / "daily.md"
    md.write_text(_good_md(), encoding="utf-8")

    def fake_render(markdown: Path, *, pdf: Path, html: Path | None = None) -> None:
        pdf.write_bytes(b"%PDF-1.7\n")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "pdfinfo":
            return FakeCompleted(cmd, stdout="Pages: 1\n")
        if cmd[0] == "pdftotext":
            Path(cmd[-1]).write_text("내부 후보 score high-heat general memo /home/jinwang/workspace\n", encoding="utf-8")
            return FakeCompleted(cmd)
        raise AssertionError(cmd)

    monkeypatch.setattr(gate, "render_pdf", fake_render)
    result = gate.run_delivery_gate(md, pdf=tmp_path / "daily.pdf", runner=fake_run)

    assert result.ok is False
    assert result.failed_stage == "first-reader-qa"
    assert any("internal/pipeline residue" in e or "reader-facing text" in e for e in result.errors)
