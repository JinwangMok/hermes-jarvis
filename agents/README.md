# agents/

Declarative agent persona definitions. Each agent manifest maps to one or more runtime handlers under `agent-shim/`; this directory must not contain platform SDK code or secrets.

## Minerva multi-agent roster

Minerva is the command governor. Boramae remains the Discord conversation surface; every execution-oriented role reports to Minerva and can be routed through Hermes Kanban.

| Agent | Myth metaphor | ZeusOS role | Kanban assignee | Primary phase |
|---|---|---|---|---|
| `minerva` | Roman wisdom / command judgment | command governor | `minerva` | all gates |
| `boramae` | messenger conversation scout | Discord dialogue surface | `boramae` | user-question |
| `artemis` | hunt / reconnaissance | research scout | `artemis` | idea_direction_explore |
| `athena` | strategic critique | plan critic | `athena` | critic_for_plan |
| `hephaestus` | forge / craft | implementation builder | `hephaestus` | execute |
| `apollo` | clarity / oracle | reviewer | `apollo` | review_align_to_goal |
| `janus` | doors / transitions | memory and evolution | `janus` | recognize_missing_gap, evolving |

Every manifest requires `selfJustification.requiredEveryPhase: true`, at least two self-questions, numeric confidence threshold, and evidence.
