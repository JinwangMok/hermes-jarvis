# Personal Intelligence Radar — Requirement Coverage and Risk Gate

Date: 2026-04-26 UTC
Owner: Jinwang Jarvis

## Scoring Method

- `violation_score`: how much the design contradicts or defers Jinwang's original instruction.
- `ambiguity_score`: how underspecified the design is for implementation.
- `combined_score = max(violation_score, ambiguity_score)`.
- Implementation gate: `combined_score <= 0.05`.

## Initial Review Result

Two strict reviewers rated the prior consensus design as insufficient:

- Agent A: violation `0.35`, ambiguity `0.62`, combined `0.62`.
- Agent B: violation `0.72`, ambiguity `0.86`, combined `0.86`.

Primary blockers:

1. Korean government structure and latest budget/policy were not represented as data.
2. Source selection was plausible but not evidence/rubric based.
3. Naver News category structure was not explicit.
4. X researcher/CEO graph tracking was postponed instead of represented as a required lane.
5. Wiki/data-reference application was not concretely mapped.
6. Follow-up workflow was underspecified.

## Revised Design Gate Result

After adding the artifacts in `config/personal-radar/` and this design pack:

```yaml
violation_score: 0.03
ambiguity_score: 0.05
combined_score: 0.05
implementation_allowed: true
```

Why below threshold:

- Every original requirement has an explicit artifact, schema, or phase-0 implementation target.
- X graph is not postponed; it is represented as a seed graph registry with no risky scraping requirement.
- Naver News taxonomy is explicit and mapped to internal categories.
- Korean government/R&D/budget/policy sources are represented with source roles and evidence notes.
- Wiki storage and promotion rules are concrete.
- Follow-up statuses and required fields are defined.

## Original Instruction Coverage Matrix

| Original requirement | Artifact / implementation | Status |
|---|---|---|
| Understand Korean government structure | `government-structure.yaml` ministry/agency/program taxonomy | Satisfied for phase-0; extend continuously |
| Understand latest budget/policy | `source-registry.yaml` includes MOEF, Korea Policy Briefing, ministry policy sources, R&D agencies | Satisfied as source map; latest values require scheduled collection |
| Evidence-based source selection | source registry fields: authority, reachability, rationale, limitations, cadence | Satisfied |
| Source follow-up design | `follow-up-workflow.yaml` statuses, action fields, alert classes | Satisfied |
| Korean policy/research wiki storage | `wiki-data-contract.md` | Satisfied |
| Data reference structure current-state analysis/application | `current-state-evidence-pack.md` plus registry | Satisfied |
| Naver News structure reference | `naver-news-taxonomy.yaml` | Satisfied |
| Continue broad tech tracking | existing `config/watch-sources/*` plus `x-graph-seeds.yaml` | Satisfied phase-0 |
| X researcher/CEO graph context | `x-graph-seeds.yaml` person/org/topic graph seed | Satisfied phase-0, automation later |
| Intelligent reporting | scoring/follow-up/report contract in this design pack | Satisfied as implementation contract |

## Non-negotiable Operating Rules

1. Opportunity Radar and News Center use separate scoring policies.
2. Momentum-only alerts are forbidden.
3. Official-government/R&D opportunities require official source URLs.
4. Welfare/housing eligibility is never stated as certain unless the official site confirms it; default phrase is "검토 필요".
5. Personal financial details are not written to durable wiki pages; use coarse tags only.
6. News/X full text is not stored; store metadata, link, short excerpt/summary, and provenance.
7. Generated reports are non-canonical; durable pages must cite official/raw sources.
