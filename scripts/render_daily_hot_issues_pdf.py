#!/usr/bin/env python3
"""Render Jinwang Jarvis daily hot-issues markdown into a polished PDF.

The renderer intentionally stays dependency-light: a small Markdown subset is converted
into HTML and then rendered with WeasyPrint. The visual language is a reader-first
business briefing: dark masthead, compact readable single-column body, issue cards,
and fixed footer.
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
  @bottom-center { content: "독자형 출처 라벨 · 사실/해석 분리"; font-size: 7.2pt; color: #94a3b8; }
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
  background: linear-gradient(135deg, #0f172a 0%, #111827 64%, #1e1b4b 100%);
  color: white;
  min-height: 52mm;
  padding: 9mm 10mm 7mm;
  margin: -1mm 0 6mm 0;
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
  font-size: 7.5pt;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #cbd5e1;
  border-bottom: 0.6pt solid rgba(255,255,255,0.36);
  padding-bottom: 3pt;
  margin-bottom: 5mm;
}
.cover-title {
  display: inline-block;
  border: 1pt solid rgba(255,255,255,0.76);
  padding: 4.5mm 6mm;
  font-weight: 900;
  font-size: 20pt;
  line-height: 1.08;
  letter-spacing: -0.04em;
  max-width: 155mm;
}
.cover-meta {
  margin-top: 3.5mm;
  color: #e5e7eb;
  font-size: 8.2pt;
}
.cover-cards {
  margin-top: 4.5mm;
}
.cover-card {
  display: inline-block;
  width: 31.5%;
  vertical-align: top;
  background: rgba(255,255,255,0.09);
  border-left: 2.2pt solid #a78bfa;
  padding: 2.5mm 3mm;
  min-height: 14mm;
  margin-right: 1.6%;
}
.cover-card b { display: block; font-size: 7.7pt; color: #ffffff; margin-bottom: 1pt; }
.cover-card span { color: #d1d5db; font-size: 7pt; }
.body-grid {
  column-count: 1;
  max-width: 178mm;
  margin: 0 auto;
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
  content: "섹션";
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


def strip_internal_appendix(md: str) -> str:
    """Remove local provenance appendices from user-facing PDF output."""
    return re.sub(r"\n## 부록: 내부 생성 근거\n.*?(?=\n## |\Z)", "", md, flags=re.S).rstrip() + "\n"


def prepare_markdown(md: str) -> str:
    return strip_internal_appendix(strip_yaml_frontmatter(md))


def extract_title(md: str) -> str:
    for line in prepare_markdown(md).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "오늘의 핫이슈"


def extract_report_time(md: str, fallback: str) -> str:
    for line in prepare_markdown(md).splitlines()[:20]:
        match = re.search(r"(?:보고 기준 시각|생성 시각|기준 시각)\s*:\s*(.+)$", line)
        if match:
            return match.group(1).strip()
    return fallback


def strip_issue_heading_number(text: str) -> str:
    """Avoid duplicated numbering when markdown headings are already numbered.

    The PDF renderer adds the visual issue number with ``data-no``. If the source
    markdown says ``### 1. Title`` or ``### 01) Title``, keeping that prefix makes
    the rendered card read like ``01 1. Title``. Strip only simple leading issue
    ordinals from issue-card headings; leave all other title text untouched.
    """
    return re.sub(r"^\s*\d{1,2}\s*[.)]\s+", "", text).strip()


def _flush_list(out: list[str], in_ul: bool) -> bool:
    if in_ul:
        out.append("</ul>")
    return False


def markdown_to_html(md: str) -> str:
    md = prepare_markdown(md)
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
            heading = line[3:].strip()
            if heading == "주요 이슈":
                continue
            out.append(f"<h2>{md_inline(heading)}</h2>")
        elif line.startswith("### "):
            close_issue_card()
            in_lead = False
            issue_no += 1
            heading = strip_issue_heading_number(line[4:])
            out.append(f'<section class="issue-card"><h3 class="issue-title" data-no="{issue_no:02d}">{md_inline(heading)}</h3>')
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
            heading = strip_issue_heading_number(text)
            out.append(f'<section class="issue-card"><h3 class="issue-title" data-no="{issue_no:02d}">{md_inline(heading)}</h3>')
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
    report_time = extract_report_time(md, now)
    body = markdown_to_html(md)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<section class="report-cover reader-first-cover">
  <div class="cover-kicker">TODAY'S HOT ISSUES · READER-FIRST BRIEFING</div>
  <div class="cover-title">{md_inline(title)}</div>
  <div class="cover-meta">보고 기준 · {html.escape(report_time)}</div>
  <div class="cover-cards">
    <div class="cover-card"><b>독자형 출처 라벨</b><span>공식·보도·주장 구분</span></div>
    <div class="cover-card"><b>사실/해석 분리</b><span>원문과 해석 구분</span></div>
    <div class="cover-card"><b>행동 가능성 검증</b><span>URL·마감·자격 확인</span></div>
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
