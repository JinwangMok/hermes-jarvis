# ZeusOS Full Pivot — Plan + MoA/Contractor Side-Effect Gate

**User request:** Remove Jarvis expressions across localhost/wiki/memory, including repo name, and pivot fully to ZeusOS.  
**Controller rule:** Do not start destructive/live mutation until contractor + MoA score is >=95 for the specific stage.

## Read-only inventory snapshot

| Surface | Jarvis-match scale | Notes |
|---|---:|---|
| `/home/jinwang/wiki` | 1824 files / 6655 matches | canonical pages + generated reports + log/index |
| `~/.hermes/skills` | 64 files / 654 matches | active skills mostly renamed; archive/reference text remains |
| `~/.hermes/config.yaml` | 1 file / 4 matches | external skill/runtime paths |
| `~/.hermes/cron` | 1802 files / 51741 matches | jobs.json + historical output archive |
| `~/workspace/jinwang-jarvis` | 5099 files / 9210 matches | repo/package/module/docs/tests/artifacts |
| `~/.config/systemd/user` | 11 files / 24 matches | live and disabled unit names/descriptions |
| persistent memory/profile | prompt-injected matches present | must be edited via memory API, not raw file rewrite |

## MoA / contractor verdicts

1. Contractor planning lane: **88/100** — feasible only after freeze, canonical naming, backups, memory export/update, and rollback gates.
2. Adversarial side-effect lane: **62/100 FAIL** — big-bang rename would break repo imports, cron, systemd, gateway plugins, wiki provenance, DB/report paths.
3. Architecture MoA lane: **93/100** — taxonomy is sound, but not safe enough for direct all-at-once execution.

**Controller convergence:** Big-bang full pivot is **FAIL-CLOSED**. Proceed only as staged cutover with per-stage >=95 gate.

## Canonical taxonomy

| Old | New canonical |
|---|---|
| `Jinwang Jarvis`, user-facing `Jarvis` | `ZeusOS` |
| `jinwang-jarvis` repo/path/package slug | `zeus-os` for repo/dist, `zeusos` for service prefix |
| `jinwang_jarvis` Python import | `zeus_os` |
| `jarvis-*` service/job/report slugs | `zeusos-*` |
| `generator: jinwang-jarvis`, `owner: jarvis`, `tags: [jarvis]` | `generator: zeusos`, `owner: zeusos`, `tags: [zeusos]` |
| `JARVIS_*` env vars | `ZEUSOS_*`, with temporary fallback only during migration |

## Stage plan and gates

### Stage 0 — Inventory, freeze plan, rollback plan
- No production mutation except planning artifacts.
- Enumerate active cron/systemd/gateway/plugin/DB/wiki/memory surfaces.
- Prepare backups and rollback commands.
- Gate PASS requires: complete manifest, owner per surface, destructive actions classified, no live side effect.

### Stage 1 — Compatibility foundation
- Add canonical `zeus_os` package/CLI while old `jinwang_jarvis` remains as temporary shim.
- Add `zeus-os` console entry; deprecate old command in help/logs only after tests pass.
- Gate PASS: old and new CLI both pass; no cron/systemd mutation; full tests pass.

### Stage 2 — Repo-local user-facing sweep
- Replace README/docs/help/report titles/user-agent/config project names.
- Keep compatibility shim/test allowlist only.
- Gate PASS: fail-bucket Jarvis zero; allowlist contains only shim/tests/migration docs; tests pass.

### Stage 3 — Skills/Hermes config/cache pivot
- Update active skills, references, `.usage.json`, skill index/cache, config external paths.
- Do not restart gateway yet; old plugin symlink stays until dry-run load passes.
- Gate PASS: skill load/search smoke, config path smoke, no broken active skill refs.

### Stage 4 — Wiki generated/current graph pivot
- Raw immutable pages are not rewritten unless explicitly marked non-canonical generated output.
- Move current generated paths to `zeusos-*`; update `index.md`, links, metadata, report generators.
- Gate PASS: link scan clean; new generated report writes to ZeusOS paths; old paths do not receive new writes.

### Stage 5 — Cron shadow migration
- Clone/update jobs to ZeusOS names/prompts/workdir/commands.
- Pause/cut over one job at a time, verify dry-run or one scheduled cycle.
- Gate PASS: no duplicate deliveries; `jobs.json` active jobs use ZeusOS commands; paused historical jobs classified.

### Stage 6 — systemd/service/gateway cutover
- Create `zeusos-*` units, stop/disable old units only after new unit smoke.
- Hermes gateway restart requires pre-armed OpenCode recovery safety belt.
- Gate PASS: new timers active, old timers inactive, gateway healthy, rollback tested.

### Stage 7 — Repo/path/remote/package cutover
- Rename local repo path to `~/workspace/zeus-os` only after cron/systemd/config no longer depend on old path.
- Update remotes after GitHub repo rename if authorized.
- Gate PASS: `python -m zeus_os.cli --help`, editable install, git status/remote clean, old path absent or approved rollback symlink only.

### Stage 8 — Persistent memory/profile pivot + final zero scan
- Use memory API to replace active Jarvis identity facts with ZeusOS facts.
- Run scans over wiki, skills, cron, config, systemd, repo, memory-export-visible surfaces.
- Gate PASS: user-facing fail-bucket zero, compatibility allowlist explicit, all smoke tests pass.

## Critical stop lines

- Do not blind-rewrite `raw/`, git history, credentials, DB binary contents, or session transcripts.
- Do not rename/delete live systemd units without stop/disable/daemon-reload/rollback gate.
- Do not restart Hermes gateway without pre-armed recovery worker.
- Do not remove `jinwang_jarvis` before all cron/systemd/plugin/import callsites use `zeus_os` and tests pass.
- Do not claim local-zero if historical cron output/session archive remains in scope; either classify as allowed immutable history or explicitly rewrite/archive with approval.

## Current gate decision

**Stage 0 planning artifact:** PASS 96/100.  
**Full direct execution:** FAIL 62/100.  
**Next allowed action:** Stage 0 detailed manifest + rollback artifact, then Stage 1 compatibility foundation only if its own MoA review reaches >=95.
