# Stage 4 Full Zero-Jarvis Cutover Gate Plan

## Controller verdict

Direct full zero-Jarvis rename/removal is **FAIL-CLOSED** for this gate.

External/MoA reviews found the current system is not safe for a single-step repo path/package/wiki/cron/systemd rewrite because:

1. `/home/jinwang/workspace/zeus-os` already exists and contains runtime `data/` and `state/`.
2. Enabled Hermes cron jobs still use `/home/jinwang/workspace/jinwang-jarvis`, `python3 -m jinwang_jarvis.cli`, and `queries/jinwang-jarvis-*` wording.
3. Live Hermes config still references repo-local skill/STT paths under `jinwang-jarvis`.
4. User systemd has active ZeusOS health timer but disabled legacy `jinwang-jarvis-*` files still exist; some inactive zeus units may contain stale test paths.
5. `zeus_os` is currently a facade over `jinwang_jarvis`; removing the backing package would break the canonical entrypoint.
6. Wiki policy forbids raw/history mass rewrite and requires review for durable page rename/archive.

## Gate scores

- Planning review: direct full-zero cutover blocked; safe staged plan required.
- Adversarial review: direct full-zero scored ~78–84/100, below the required 95.

## Allowed next sequence

### Stage 4A — freeze + sanitized manifest
- Pause/update only affected ZeusOS/Jarvis cron surfaces with rollback.
- Capture sanitized live state, not raw secrets/config dumps.
- Inventory `/home/jinwang/workspace/zeus-os` runtime data before moving anything.

### Stage 4B — cron command/prompt cutover while repo path remains legacy
- Keep `workdir=/home/jinwang/workspace/jinwang-jarvis` until repo-path collision is resolved.
- Replace live cron commands with `python3 -m zeus_os.cli` and ZeusOS wording.
- Re-enable one canary job at a time after smoke checks.

### Stage 4C — wiki canonical migration without raw rewrite
- Create/update canonical ZeusOS entity/query pages.
- Keep old Jarvis pages as legacy bridge/redirect notes where useful.
- Do not rewrite `raw/`, historical logs, or backups.

### Stage 4D — Hermes config/systemd path cleanup
- Update external skill/STT paths only after repo-path decision.
- Clean disabled legacy user units; ensure active health timer remains unique.

### Stage 4E — repo path/data collision resolution
- Decide whether existing `/home/jinwang/workspace/zeus-os` runtime data is merged, archived, or promoted as external runtime root.
- Only then move repo path and install a temporary compatibility symlink if needed.

### Stage 4F — package/distribution cutover
- First invert implementation so `zeus_os` is primary and `jinwang_jarvis` becomes shim.
- Remove shim only after external consumer audit and a separate major compatibility gate.

## Current status

Stage 1–3 are complete at commit `ce6fb53`.
Stage 4 is started but direct full-zero is intentionally blocked pending staged remediation.
