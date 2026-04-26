#!/usr/bin/env python3
"""Render Jinwang Jarvis daily hot-issues markdown into a polished PDF.

The renderer intentionally stays dependency-light: a small Markdown subset is converted
into HTML and then rendered with WeasyPrint. The visual language is a newspaper-like
business report: dark masthead, compact readable columns, issue cards, and fixed footer.
"""
from __future__ import annotations

import argparse
import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

CSS = """
@page {
  size: A4;
  margin: 12mm 11mm 15mm 11mm;
  @bottom-left { content: "Jinwang Jarvis · 오늘의 핫이슈"; font-size: 7.5pt; color: #64748b; }
  @bottom-center { content: "generated daily intelligence brief"; font-size: 7.2pt; color: #94a3b8; }
  @bottom-right { content: "page " counter(page); font-size: 7.5pt; color: #64748b; }
}
:root {
  --ink: #111827;
  --muted: #64748b;
  --navy: #111827;
  --navy2: #1f2937;
  --line: #cbd5e1;
  --paper: #f8fafc;
  --card: #f1f5f9;
  --accent: #7c3aed;
  --accent2: #0f766e;
}
* { box-sizing: border-box; }
body {
  font-family: 'Noto Sans CJK KR', 'Noto Sans KR', 'Apple SD Gothic Neo', 'DejaVu Sans', sans-serif;
  color: var(--ink);
  line-height: 1.42;
  font-size: 8.9pt;
  word-break: keep-all;
  overflow-wrap: anywhere;
  background: white;
}
a { color: #1d4ed8; text-decoration: none; }
code {
  font-family: 'Noto Sans Mono CJK KR', 'DejaVu Sans Mono', monospace;
  background: #e5e7eb;
  padding: 0.5pt 3pt;
  border-radius: 3pt;
  font-size: 8pt;
}
.report-cover {
  background: linear-gradient(135deg, #0f172a 0%, #111827 62%, #312e81 100%);
  color: white;
  min-height: 80mm;
  padding: 13mm 12mm 10mm;
  margin: -1mm 0 8mm 0;
  position: relative;
  overflow: hidden;
}
.report-cover:before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(0deg, rgba(255,255,255,0.035) 1px, transparent 1px);
  background-size: 16mm 16mm;
  opacity: 0.85;
}
.cover-kicker, .cover-title, .cover-meta, .cover-cards { position: relative; z-index: 1; }
.cover-kicker {
  font-size: 8pt;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #cbd5e1;
  border-bottom: 0.6pt solid rgba(255,255,255,0.42);
  padding-bottom: 4pt;
  margin-bottom: 10mm;
}
.cover-title {
  display: inline-block;
  border: 1.2pt solid rgba(255,255,255,0.82);
  padding: 7mm 9mm;
  font-weight: 900;
  font-size: 26pt;
  line-height: 1.08;
  letter-spacing: -0.04em;
  max-width: 150mm;
}
.cover-meta {
  margin-top: 6mm;
  color: #e5e7eb;
  font-size: 9pt;
}
.cover-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4mm;
  margin-top: 9mm;
}
.cover-card {
  background: rgba(255,255,255,0.10);
  border-left: 3pt solid #a78bfa;
  padding: 4mm;
  min-height: 22mm;
}
.cover-card b { display: block; font-size: 8pt; color: #ffffff; margin-bottom: 2pt; }
.cover-card span { color: #d1d5db; font-size: 7.6pt; }
.body-grid {
  column-count: 2;
  column-gap: 9mm;
  column-rule: 0.4pt solid #e2e8f0;
}
.reader-note, .action-checklist {
  column-span: all;
  border: 0.7pt solid #cbd5e1;
  background: #f8fafc;
  padding: 4mm 5mm;
  margin: 0 0 5mm;
}
.issue-card {
  display: block;
  break-inside: avoid;
  page-break-inside: avoid;
  margin: 0 0 4mm;
  padding: 0 0 2.5mm;
  border-bottom: 0.4pt solid #e5e7eb;
}
.issue-card ul { margin-bottom: 0; }
h1 { display: none; }
h2 {
  column-span: all;
  margin: 6mm 0 3mm;
  padding: 3.2mm 4mm;
  background: var(--navy);
  color: white;
  font-size: 12.5pt;
  letter-spacing: -0.02em;
  break-after: avoid;
}
h2:before {
  content: "SECTION";
  display: inline-block;
  font-size: 6pt;
  letter-spacing: 0.18em;
  color: #c4b5fd;
  margin-right: 5mm;
  vertical-align: middle;
}
h3 {
  break-inside: avoid;
  margin: 4.5mm 0 2.2mm;
  padding: 3mm 3.2mm 2.5mm;
  background: var(--card);
  border-top: 2pt solid var(--navy2);
  font-size: 10.4pt;
  line-height: 1.26;
}
h3.issue-title:before {
  content: attr(data-no);
  display: inline-block;
  min-width: 8mm;
  margin-right: 2mm;
  color: var(--accent);
  font-weight: 900;
}
p {
  margin: 0 0 2.2mm;
  text-align: justify;
}
ul, ol { margin: 0 0 3mm 0; padding-left: 4.8mm; }
li { margin: 0 0 1.3mm; }
li strong:first-child {
  color: #0f172a;
}
.lead-block {
  column-span: all;
  background: #f8fafc;
  border-left: 4pt solid var(--accent2);
  padding: 4mm 5mm;
  margin: 0 0 5mm;
  font-size: 10pt;
  line-height: 1.48;
}
.lead-block p { margin: 0 0 2mm; text-align: left; }
.source-note {
  column-span: all;
  border: 0.6pt solid var(--line);
  background: white;
  padding: 3.5mm;
  color: var(--muted);
  font-size: 7.8pt;
}
hr { border: none; border-top: 0.5pt solid #e5e7eb; margin: 4mm 0; }
"""


def md_inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def strip_yaml_frontmatter(md: str) -> str:
    """Remove YAML frontmatter before rendering human-facing PDF pages."""
    if md.startswith("---\n"):
        end = md.find("\n---\n", 4)
        if end != -1:
            return md[end + len("\n---\n"):].lstrip()
    return md


def extract_title(md: str) -> str:
    for line in strip_yaml_frontmatter(md).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "오늘의 핫이슈"


def _flush_list(out: list[str], in_ul: bool) -> bool:
    if in_ul:
        out.append("</ul>")
    return False


def markdown_to_html(md: str) -> str:
    md = strip_yaml_frontmatter(md)
    out: list[str] = []
    in_ul = False
    skipped_first_h1 = False
    issue_no = 0
    in_lead = True
    in_issue_card = False

    def close_issue_card() -> None:
        nonlocal in_issue_card, in_ul
        in_ul = _flush_list(out, in_ul)
        if in_issue_card:
            out.append("</section>")
            in_issue_card = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line:
            in_ul = _flush_list(out, in_ul)
            continue
        if line.startswith("# "):
            close_issue_card()
            if not skipped_first_h1:
                skipped_first_h1 = True
                continue
            out.append(f"<h1>{md_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            close_issue_card()
            in_lead = False
            out.append(f"<h2>{md_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            close_issue_card()
            in_lead = False
            issue_no += 1
            out.append(f'<section class="issue-card"><h3 class="issue-title" data-no="{issue_no:02d}">{md_inline(line[4:])}</h3>')
            in_issue_card = True
        elif line.startswith("- "):
            if in_lead:
                in_ul = _flush_list(out, in_ul)
                out.append(f'<p class="lead-line">• {md_inline(line[2:])}</p>')
            else:
                if not in_ul:
                    out.append("<ul>")
                    in_ul = True
                out.append(f"<li>{md_inline(line[2:])}</li>")
        elif re.match(r"^\d+\.\s+", line):
            close_issue_card()
            in_lead = False
            text = re.sub(r"^\d+\.\s+", "", line)
            issue_no += 1
            out.append(f'<section class="issue-card"><h3 class="issue-title" data-no="{issue_no:02d}">{md_inline(text)}</h3>')
            in_issue_card = True
        else:
            in_ul = _flush_list(out, in_ul)
            if in_lead:
                out.append(f'<p class="lead-line">{md_inline(line)}</p>')
            else:
                out.append(f"<p>{md_inline(line)}</p>")
    close_issue_card()

    html_text = "\n".join(out)
    # Put initial metadata bullets in a full-width lead block until the first h2.
    if "<h2>" in html_text:
        lead, rest = html_text.split("<h2>", 1)
        if lead.strip():
            return f'<div class="lead-block">\n{lead}\n</div>\n<h2>{rest}'
    return html_text


def render_document(md: str, now: str) -> str:
    title = extract_title(md)
    body = markdown_to_html(md)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<section class="report-cover">
  <div class="cover-kicker">TODAY'S HOT ISSUES · BUSINESS INTELLIGENCE REPORT</div>
  <div class="cover-title">{md_inline(title)}</div>
  <div class="cover-meta">Generated by Jinwang Jarvis · {html.escape(now)}</div>
  <div class="cover-cards">
    <div class="cover-card"><b>원문·공식 발표 우선</b><span>제목/반응보다 출처가 실제로 말한 내용 중심</span></div>
    <div class="cover-card"><b>연결 맥락</b><span>기업·정책·시장·기회 소스를 독자 언어로 설명</span></div>
    <div class="cover-card"><b>오늘의 체크리스트</b><span>지금 할 일/이번 주 확인/보류 항목 분리</span></div>
  </div>
</section>
<main class="body-grid">
{body}
</main>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown", type=Path)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--html", type=Path)
    args = ap.parse_args()
    md = args.markdown.read_text(encoding="utf-8")
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    doc = render_document(md, now)
    html_path = args.html or args.pdf.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(doc, encoding="utf-8")
    from weasyprint import HTML
    HTML(filename=str(html_path)).write_pdf(str(args.pdf))
    print(args.pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
