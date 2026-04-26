# Personal Radar source collection pipelines

Operational mirror of `/home/jinwang/wiki/_meta/source-registry/personal-radar-source-pipelines.md` for developers working in this repo.

## Rule
For opportunity sources, never report from headline-only metadata. Collect enough original-source detail to preserve:
- original title
- owner/agency
- target audience or eligibility text
- deadline/application window
- support contents
- attachment URLs
- raw excerpt
- uncertainty/manual-check fields

## Site strategy summary

| source_id | collection path |
|---|---|
| moef-home | sitemap.xml discovery, then budget/policy/press detail HTML |
| korea-policy-briefing | sitemap.xml discovery; homepage can reset simple HTTP |
| gov24 | service/subsidy search pages or public API candidate; login-free metadata only |
| msit-home | fixed MSIT board/list URLs for notices/press/business announcements |
| iris | R&D notice/search board endpoint; ignore fake sitemap HTML response |
| ntis | sitemap.xml + search/detail pages as duplicate verifier |
| iitp | business announcement board parser + attachment extraction |
| nipa | business announcement board parser + AI/SW/cloud keyword filter |
| nrf | notice/business board parser; PDF attachment required for eligibility |
| k-startup | startup support program search/list parser; extract deadline/target |
| bizinfo | broad support-project search/list parser with fit scoring |
| youthcenter | youth-policy search/list parser; age/region/status as separate fields |
| bokjiro | welfare service search/list or public API; never overclaim personal eligibility |
| myhome | housing welfare/public rental list/detail parser |
| lh-apply | LH notice list/detail + PDF attachment parser |
| applyhome | subscription calendar/notice parser; region/type/window extraction |
| housing-fund | sitemap.xml + loan/product/notice detail parser |
| naver-news | metadata-only RSS/search; no full article storage |

## Report quality
Daily reports must include a `원문 내용` or `source_content_summary` field before `왜 중요한가`. Quantitative reaction metrics are supporting evidence only.
