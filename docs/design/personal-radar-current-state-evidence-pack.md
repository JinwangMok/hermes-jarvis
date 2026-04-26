# Current-State Evidence Pack — Korean Policy, Opportunity, News, and Tech Radar

Date: 2026-04-26 UTC

## Live Reachability Probe

A lightweight HTTP probe was run from OpenBox with a personal research User-Agent. Results:

| Source | Result | Interpretation |
|---|---|---|
| gov.kr | 200 | usable landing source; specific APIs/pages still need per-endpoint validation |
| IRIS | 200 | reachable canonical R&D application/system source |
| NTIS | 200 | reachable national R&D information source |
| IITP | 200 | reachable ICT R&D agency source |
| NIPA | 200 | reachable SW/AI/cloud agency source |
| NRF | 200 | reachable research foundation source |
| K-Startup | 200 | reachable startup support source |
| 기업마당 | 200 | reachable SME/support integrated source |
| 온통청년 | 200 | reachable youth policy source |
| 마이홈 | 200 | reachable housing welfare source |
| LH 청약플러스 | 200 | reachable public housing application source |
| 청약홈 | 200 | reachable housing subscription source |
| 주택도시기금 | 200 | reachable housing finance policy source |
| Naver News | 200 | reachable category/news index source |
| X | 200 | reachable landing surface; API/auth policy still governs collection |
| MOEF / Korea.kr / MSIT / Bokjiro | connection reset in simple probe | do not treat as unavailable; use browser/API/fallback and lower probe frequency |

## Current-State Assessment by Domain

### Korean government and budget/policy

Canonical structure must start from ministries and official policy/budget channels, not media reports. MOEF and Korea Policy Briefing are budget/policy origin references; ministry sites and affiliated agencies are program owners. Some sites reset simple HTTP connections, so the collector must support staged/manual/browser verification and not assume failure equals source absence.

### R&D and research programs

R&D is multi-layered:

- policy/budget owner: MOEF + related ministry,
- ministry program owner: MSIT, MOTIE, MOLIT, MOE, MSS, etc.,
- agency/operator: IITP, NIPA, NRF, KIAT, KEIT, TIPA, KISTI, NIA,
- application/project system: IRIS, NTIS, SMTECH, agency portals,
- local execution path: university research office / 산학협력단.

For Jinwang, MSIT/IITP/NIPA/NRF/IRIS/NTIS are P0 because they directly connect to AI, cloud, software, and university research work.

### Startup/commercialization

K-Startup, 기업마당, MSS, TIPA/SMTECH, KISED and regional startup/economic agencies should be matched to whether Jinwang has a company, team, university affiliation, or only a pre-startup intent.

### Youth/welfare/housing/subscription

Eligibility depends on residence, household, income, assets, student/employment status, and sometimes military status. With current profile, the system may rank candidates but must produce `missing_user_info` and `needs_manual_check` unless official forms confirm eligibility.

### Korean news / Naver reference

Naver News should be used as a category/taxonomy and agenda-detection reference, not necessarily as the only raw source. It helps map Korean discourse into politics, economy, society, life/culture, world, IT/science, opinion. Official policy pages remain canonical for facts.

### Global AI/cloud/Agentic AI and X graph

Existing external hot-issues sources already cover many official/blog/community sources. The missing phase-0 piece is a durable seed graph of people, orgs, projects, and topics, including X handles where known. Until API/auth is stable, X content is supporting evidence only.
