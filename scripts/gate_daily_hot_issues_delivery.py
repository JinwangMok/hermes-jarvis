#!/usr/bin/env python3
"""End-to-end delivery gate for reader-facing Daily Hot Issues PDFs.

Hard-fail sequence:
1. content lint on markdown
2. PDF render
3. pdfinfo structural check
4. pdftotext -layout extraction
5. first-reader QA on extracted text
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_linter = _load_script_module("lint_daily_hot_issues_content", ROOT / "scripts" / "lint_daily_hot_issues_content.py")
_renderer = _load_script_module("render_daily_hot_issues_pdf", ROOT / "scripts" / "render_daily_hot_issues_pdf.py")

Runner = Callable[..., subprocess.CompletedProcess[str]]


class GateResult:
    def __init__(
        self,
        ok: bool,
        *,
        markdown: Path,
        pdf: Path,
        html: Path | None = None,
        text: Path | None = None,
        failed_stage: str | None = None,
        errors: list[str] | None = None,
        pdfinfo: str = "",
    ) -> None:
        self.ok = ok
        self.markdown = markdown
        self.pdf = pdf
        self.html = html
        self.text = text
        self.failed_stage = failed_stage
        self.errors = errors or []
        self.pdfinfo = pdfinfo


FIRST_READER_REQUIRED_TERMS = [
    "오늘의 핫이슈",
    "출처 성격",
    "확인된 사실",
    "왜 중요한가",
    "오늘 할 일",
    "근거",
    "불확실성",
]
FIRST_READER_BANNED_PATTERNS = [
    (re.compile(r"/home/jinwang|/workspace|(?:jinwang-jarvis|zeus-os)/data", re.I), "local path leaked"),
    (re.compile(r"\b(high-heat|low-heat|weak signal|score|momentum|importance|deduped|fetch(?:ed)?|registry|source audit)\b", re.I), "internal/pipeline residue"),
    (re.compile(r"검증 전 후보|내부 후보|일반론|분류\s*:|열기\s*:|중요도\s*\d"), "internal/pipeline residue"),
]


def render_pdf(markdown: Path, *, pdf: Path, html: Path | None = None) -> None:
    """Render markdown to PDF using the project renderer."""
    md = markdown.read_text(encoding="utf-8")
    now = _renderer.datetime.now(_renderer.KST).strftime("%Y-%m-%d %H:%M KST")
    doc = _renderer.render_document(md, now)
    html_path = html or pdf.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(doc, encoding="utf-8")
    from weasyprint import HTML

    HTML(filename=str(html_path)).write_pdf(str(pdf))


def _run_command(runner: Runner, cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return runner(list(cmd), text=True, capture_output=True)


def _fail(markdown: Path, pdf: Path, html: Path | None, text: Path | None, stage: str, errors: list[str]) -> GateResult:
    return GateResult(False, markdown=markdown, pdf=pdf, html=html, text=text, failed_stage=stage, errors=errors)


def _pdf_pages(pdfinfo_output: str) -> int | None:
    match = re.search(r"^Pages:\s*(\d+)\s*$", pdfinfo_output, re.M)
    return int(match.group(1)) if match else None


def first_reader_qa(extracted_text: str, *, source_markdown: str = "") -> list[str]:
    """Check whether the PDF text is readable as a first-reader artifact.

    PDF text extraction often drops clickable hyperlink targets, so source URL
    presence is accepted from the original markdown while the reader-facing cues
    are still checked on the extracted PDF text.
    """
    errors: list[str] = []
    normalized = re.sub(r"\s+", " ", extracted_text).strip()
    if len(normalized) < 180:
        errors.append("reader-facing text is too short after PDF extraction")
    for term in FIRST_READER_REQUIRED_TERMS:
        if term not in extracted_text:
            errors.append(f"reader-facing text missing required cue: {term}")
    if not re.search(r"https?://", extracted_text) and not re.search(r"https?://", source_markdown):
        errors.append("reader-facing text missing external source URL")
    for pattern, label in FIRST_READER_BANNED_PATTERNS:
        match = pattern.search(extracted_text)
        if match:
            errors.append(f"{label}: {match.group(0)}")
    return errors


def run_delivery_gate(
    markdown: Path,
    *,
    pdf: Path | None = None,
    html: Path | None = None,
    text: Path | None = None,
    runner: Runner = subprocess.run,
) -> GateResult:
    markdown = Path(markdown)
    pdf = Path(pdf) if pdf is not None else markdown.with_suffix(".pdf")
    html = Path(html) if html is not None else pdf.with_suffix(".html")
    text = Path(text) if text is not None else pdf.with_suffix(".txt")

    lint_errors = _linter.lint_text(markdown.read_text(encoding="utf-8"))
    if lint_errors:
        return _fail(markdown, pdf, html, text, "content-lint", ["daily hot-issues content lint failed", *lint_errors])

    try:
        render_pdf(markdown, pdf=pdf, html=html)
    except Exception as exc:  # pragma: no cover - exact dependency failures vary by host
        return _fail(markdown, pdf, html, text, "render-pdf", [str(exc)])

    info = _run_command(runner, ["pdfinfo", str(pdf)])
    if info.returncode != 0:
        return _fail(markdown, pdf, html, text, "pdfinfo", [info.stderr.strip() or info.stdout.strip() or "pdfinfo failed"])
    pages = _pdf_pages(info.stdout)
    if pages is None or pages < 1:
        return _fail(markdown, pdf, html, text, "pdfinfo", [f"invalid or missing page count: {pages!r}"])

    extracted = _run_command(runner, ["pdftotext", "-layout", str(pdf), str(text)])
    if extracted.returncode != 0:
        return _fail(markdown, pdf, html, text, "pdftotext", [extracted.stderr.strip() or extracted.stdout.strip() or "pdftotext -layout failed"])
    extracted_text = text.read_text(encoding="utf-8", errors="replace") if text.exists() else ""
    qa_errors = first_reader_qa(extracted_text, source_markdown=markdown.read_text(encoding="utf-8"))
    if qa_errors:
        return _fail(markdown, pdf, html, text, "first-reader-qa", qa_errors)

    return GateResult(True, markdown=markdown, pdf=pdf, html=html, text=text, pdfinfo=info.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(description="Hard-fail Daily Hot Issues delivery gate")
    ap.add_argument("markdown", type=Path)
    ap.add_argument("--pdf", type=Path)
    ap.add_argument("--html", type=Path)
    ap.add_argument("--text", type=Path)
    args = ap.parse_args()
    result = run_delivery_gate(args.markdown, pdf=args.pdf, html=args.html, text=args.text)
    if not result.ok:
        print(f"daily hot-issues delivery gate failed at {result.failed_stage}:", file=sys.stderr)
        for err in result.errors:
            print(f"- {err}", file=sys.stderr)
        return 1
    print(f"daily hot-issues delivery gate passed: {result.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
