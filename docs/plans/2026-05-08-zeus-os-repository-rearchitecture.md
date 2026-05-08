# ZeusOS Repository Rearchitecture Implementation Plan

> **For Hermes:** Use incremental-spec-driven-execution and subagent-driven-development before moving real files. This plan is the non-destructive migration contract for Jinwang-approved option B: plan + new branch + empty scaffold only.

**Goal:** Reorganize `zeus-os` into a template-based, extensible, declarative Agent OS workspace without breaking the current `zeus_os` CLI, runtime state, data artifacts, cron/watchdog behavior, or Hermes source-untouched boundary.

**Architecture:** The target repo separates declarative identity (`agents/`), platform bindings (`agent-shim/`), extensible capabilities (`apps/`), user-facing channels (`channels/`), volatile/session memory (`vmem/`), staged knowledge (`journals/`), durable wiki (`wiki/`), generated assets (`assets/`), secrets (`credentials/`), and the default work area (`workspace/`). Current Python package code remains under `src/zeus_os` until compatibility contracts and migration tests are accepted.

**Tech Stack:** Python 3.11+, YAML/Markdown declarative manifests, SQLite runtime state, Hermes user plugin/shim boundary, cron-compatible watchdog scripts, gitignored local secret/runtime directories.

---

## 0. Current live constraints

- Branch for this work: `feature/zeus-os-repository-rearchitecture`.
- Existing dirty work was present before branch creation; do not mix unrelated mail-secretary/runtime edits into scaffold commits.
- Existing root `Spec.md` is an old mail/calendar MVP execution spec and must not be overwritten in this step.
- Runtime truth currently exists under `state/` and `data/`; do not move these without migration map + rollback.
- Hermes core, `~/.hermes`, systemd, live cron, raw wiki, and credentials are out of scope unless Jinwang explicitly approves.

## 1. Target top-level layout contract

```text
zeus-os/
  agents/                         # declarative agent persona definitions
  agent-shim/                     # runtime/platform dependency handlers
    hermes/
    pi/
    openclaw/
    ironclaw/
    roach-pi/
  apps/                           # extensible capabilities
    watchdogs/
      email-handler/
      news-center/
      update-handler/
      dialog-pattern-analysis/
      compact-knowledge-base/
      journal-to-wiki/
    skill-sets/
      external-skills/
        k-skill/
      custom-skills/
        minerva/                  # future rename target for hooo/houroboros
    mcps/
    tools/
      custom-defined-tools/
        tmux-manager/
        email-sender/
        opencode-manager/
        claude-code-manager/
    a2a/
  channels/
    discord/
    kakaotalk/
    emails/
  vmem/                           # volatile memory; TTL/session-cleanable
  journals/                       # staged knowledge before wiki promotion
  wiki/                           # long-term wiki-style memory
  assets/
    tmp/
    archive/
      ArchiveLists.md
  credentials/                    # gitignored secrets root
    user-secrets/
    api-keys/
    channel-secrets/
  workspace/                      # default user working area
```

## 2. Naming and responsibility decisions

| Area | Responsibility | Current source / migration note |
|---|---|---|
| `agents/` | Persona definitions only, no runtime SDK dependency | New declarative manifests; each agent maps to one or more `agent-shim/*` entries |
| `agent-shim/` | Adapter contracts for Hermes, Pi, OpenClaw, IronClaw, Roach-Pi | Do not move Hermes plugin yet; document interface first |
| `apps/watchdogs/` | Cron/watch loop apps | Current `scripts/*watchdog*` and news/mail jobs migrate here after tests |
| `apps/skill-sets/` | External/custom skills | Current `skills/` remains compatibility path until loader contract is rewritten |
| `apps/skill-sets/custom-skills/minerva/` | Future HOOO/Houroboros home | Do not rename `skills/hooo` yet; create placeholder only |
| `apps/mcps/` | MCP server configs/adapters | Empty scaffold until native MCP contracts are known |
| `apps/tools/custom-defined-tools/` | Tool adapters/managers | Future tmux/email/opencode/claude-code managers live here |
| `apps/a2a/` | A2A blackboard/orchestrator capability | Align with ZeusOS Discord Boardroom A2A Blackboard concept |
| `channels/` | Direct user-message surfaces | Discord/KakaoTalk/email render/send adapters |
| `vmem/` | Volatile online memory | Must have TTL/cleanup policy before use |
| `journals/` | Staged knowledge before wiki | `journal-to-wiki` should polish/promote daily |
| `wiki/` | Durable long-term memory | Current external `~/wiki` remains canonical until migration approved |
| `assets/` | Generated files and attachments | `tmp/` for new files, `archive/` for retained assets |
| `credentials/` | Local secrets only | Must stay gitignored; only placeholder policy files may be tracked |
| `workspace/` | Default user working area | Repo clones, push work, scratch tasks; no secrets by default |

## 3. Compatibility strategy

1. Keep `src/zeus_os` package and `zeus-os` CLI stable during early migration.
2. Add path-resolution layer later so old paths (`data/`, `state/`, `skills/`, `scripts/`) and new app paths can coexist.
3. Move only one responsibility at a time, with:
   - inventory of current files,
   - target path,
   - compatibility shim,
   - rollback command,
   - targeted test.
4. Treat `data/` and `state/` as runtime truth; never bulk move them in the same commit as scaffolding.
5. Keep `~/wiki` canonical until `wiki/` migration has explicit source-of-truth policy.

## 4. Execution phases

### Phase 0 — Non-destructive scaffold (current approved B)
- Create empty target directories with `.gitkeep` where needed.
- Add short `README.md` contracts to major roots.
- Add `.gitignore` rules for `credentials/**`, `vmem/**`, `assets/tmp/**`, and `workspace/**` while preserving placeholder docs.
- Do not move existing files.

### Phase 1 — Declarative contracts
- Define manifest schema for `agents/*.yaml`.
- Define `agent-shim/*/README.md` interface contract.
- Define `apps/*/README.md` capability contract.
- Add validation tests that only inspect declarations.

Status after Jinwang-approved follow-up B:
- Added schema docs: `docs/schemas/agent-persona.schema.yaml`, `docs/schemas/capability-app.schema.yaml`.
- Added sample declarations: `agents/boramae.yaml`, `apps/watchdogs/news-center/app.yaml`, `apps/skill-sets/custom-skills/minerva/app.yaml`, `apps/a2a/app.yaml`, `channels/discord/app.yaml`.
- Added validator module: `src/zeus_os/declarative.py`.
- Added tests: `tests/test_declarative_manifests.py`.
- Verified with TDD RED/GREEN: missing validator failed first, missing schema docs failed first, then `PYTHONPATH=src pytest -q tests/test_declarative_manifests.py` passed.

### Aggressive Acceptance — defendable target state

This migration should not stop at a cosmetic directory scaffold. The accepted end state is:

1. **Declarative control plane first:** `agents/`, `agent-shim/`, `apps/`, and `channels/` manifests become the primary registry for ZeusOS-owned capabilities; legacy paths remain compatibility surfaces, not the design center.
2. **Runtime reads the registry:** phase exit requires at least one concrete ZeusOS-owned runtime caller to read canonical metadata through the declarative registry while preserving old fallback behavior; final migration acceptance requires every migrated capability to be registry-driven.
3. **Compatibility is explicit, not implicit:** every old root (`data/`, `state/`, `skills/`, `scripts/`) has a named resolver rule, source-of-truth status, rollback note, and regression test.
4. **No destructive truth moves:** `data/` and `state/` remain in place until there is an inventory, migration map, dry-run verifier, rollback command, and post-move smoke test.
5. **Every moved capability is app-shaped:** a migrated watchdog/skill/tool/channel must have an `app.yaml`, entrypoint, validation test, compatibility alias if needed, and runtime smoke evidence.
6. **Hermes boundary stays clean:** Hermes source, `~/.hermes`, gateway, systemd, cron, raw wiki, and credentials are not modified unless a separate approval explicitly names them.
7. **Secrets remain unrepresentable:** manifests may reference credential handles, never secret values; tests must fail on obvious secret-like values in tracked declarative files.
8. **Operator evidence is mandatory:** each leaf migration records commands, test output, diff scope, and reviewer verdict before the next leaf starts.

### Defensive review model

Before each implementation leaf is accepted:

1. **Spec review:** a fresh reviewer checks whether the leaf obeys this plan, touches only allowed paths, and advances the aggressive acceptance criteria.
2. **Safety review:** verify no secret persistence, no raw wiki writes, no runtime truth move, no cron/systemd/gateway side effects, and no unrelated dirty files staged.
3. **Compatibility review:** prove old CLI/path behavior still works or that the change is behind an explicit compatibility shim.
4. **Test review:** require RED -> GREEN evidence for new behavior plus targeted regression tests for existing behavior.
5. **Diff review:** inspect staged diff only; unrelated pre-existing dirty work must remain excluded.
6. **Rollback review:** every migration leaf must name a concrete rollback command or no-op rollback reason.

### Phase 2 — Compatibility path resolver
- Implement `zeus_os.paths` or equivalent as the compatibility firewall between old roots and new declarative roots.
- Add tests proving existing CLI/data/state behavior remains unchanged.
- Add tests proving new declarative roots can be resolved without moving runtime truth.
- Document environment overrides, source-of-truth status, and rollback expectations.
- Acceptance for Phase 2: runtime can ask one resolver API for `data`, `state`, `skills`, `scripts`, `apps`, `channels`, `agents`, and `agent_shim` roots; no caller hardcodes migration assumptions.

### Phase 3 — Skill/app migration
- Introduce `apps/skill-sets/custom-skills/minerva/` as canonical future HOOO location.
- Keep compatibility bridge from `skills/hooo` until loader migration is verified.
- Migrate one skill at a time.

### Phase 4 — Watchdog/app migration
- Migrate `scripts/mail-secretary-watchdog.py` and news-center flows into `apps/watchdogs/*` one by one.
- Keep current cron/systemd entries unchanged until explicit cutover approval.

### Phase 5 — Channels and A2A
- Formalize `channels/discord`, `channels/kakaotalk`, `channels/emails` contracts.
- Align `apps/a2a` with the blackboard/orchestrator design.

### Phase 6 — Memory and asset lifecycle
- Implement TTL policy for `vmem`.
- Implement `journals -> wiki` promotion workflow.
- Implement asset archive policy and `ArchiveLists.md` updates.

## 5. Immediate acceptance for option B

- [ ] Branch exists: `feature/zeus-os-repository-rearchitecture`.
- [ ] This plan exists under `docs/plans/2026-05-08-zeus-os-repository-rearchitecture.md`.
- [ ] Target scaffold directories exist.
- [ ] No existing runtime file is moved.
- [ ] `credentials/`, `vmem/`, `assets/tmp/`, and `workspace/` contents are ignored except placeholder policy files.
- [ ] `git status` clearly separates pre-existing dirty work from this scaffold.

## 6. Next approval gate

After option B, do **not** proceed to migration. Ask Jinwang to choose:

A. Review/refine naming and contracts only.
B. Add declarative schemas/tests for manifests.
C. Start first real migration leaf, probably path resolver or `minerva` skill bridge.
```
