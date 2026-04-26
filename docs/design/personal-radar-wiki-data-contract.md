# Personal Intelligence Radar — Wiki/Data Reference Contract

## Storage Authority

| Layer | Role | Canonical? |
|---|---|---|
| SQLite / JSON artifacts | operational source of truth for runs, signals, scores | yes for runtime state |
| `raw/` | immutable evidence snapshots where legally safe | evidence only |
| `reports/` | generated daily/hourly dashboards | non-canonical |
| `entities/` | durable org/person/program/entity pages | canonical synthesis if source-linked |
| `concepts/` | durable models: Korean R&D structure, housing policy, scoring rules | canonical synthesis if source-linked |
| `queries/` | durable answers and design investigations | durable, not raw evidence |
| `_meta/source-registry/` | source inventory and collection policy | operational metadata |
| `_meta/runs/` | run metadata and provenance | operational metadata |

## Recommended Wiki Paths

```text
_meta/source-registry/personal-radar-sources.md
_meta/source-registry/naver-news-taxonomy.md
_meta/source-registry/x-graph-seeds.md
_meta/runs/YYYY-MM-DD/personal-radar-run-id.md
concepts/korean-government-rnd-policy-structure.md
concepts/personal-opportunity-radar-operating-model.md
concepts/korean-news-center-taxonomy.md
queries/personal-intelligence-radar-design-april-2026.md
reports/opportunity-radar/index.md
reports/news-center/index.md
reports/news-center/categories/{politics,economy,society,it-science,world}.md
```

## Generated Report Frontmatter

```yaml
generated: true
authority: generated
canonical: false
generator: jinwang-jarvis-personal-radar
operational_source_of_truth: state/personal_intel.db
allowed_use: triage_only
promotion_policy: source-linked compressed facts only
```

## Promotion Rule

A generated item may be promoted into durable wiki knowledge only when:

1. the official/source URL is present,
2. the fact is compressed and not copied wholesale,
3. the destination page cites the official/raw source, not only the report,
4. uncertainty and missing user info are preserved,
5. the log records the promotion.

## Privacy Rule

Durable pages may store coarse policy-matching tags only:

- `청년`
- `무주택`
- `청약통장_보유`
- `저축_낮음`
- `대학원생`
- `ai-cloud-research`

Do not store exact private financial values in durable wiki text unless Jinwang explicitly requests it for that page.
