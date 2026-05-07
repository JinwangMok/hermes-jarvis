# Stage 4B Cron Surface Cutover Result

## Scope

Live Hermes cron metadata was updated to stop re-injecting user-facing Jarvis wording and legacy module commands while keeping the current repo workdir stable.

## Safety boundary

- `workdir` remains `/home/jinwang/workspace/zeus-os` because the repo-path cutover is blocked by the existing `/home/jinwang/workspace/zeus-os` runtime data directory.
- Raw cron backup was written outside the git repo under `~/.hermes/backups/zeusos-stage4-*/`.
- No gateway restart was performed.

## Changes applied

Replaced, inside `~/.hermes/cron/jobs.json`:

- `python3 -m jinwang_jarvis.cli` → `python3 -m zeus_os.cli`
- `python -m jinwang_jarvis.cli` → `python -m zeus_os.cli`
- `jinwang_jarvis.cli` → `zeus_os.cli`
- `queries/jinwang-jarvis-intelligence` → `queries/zeus-os-intelligence`
- `queries/jinwang-jarvis-memory` → `queries/zeus-os-memory`
- `Jinwang Jarvis` / `Jarvis` in prompts → `ZeusOS`

## Verification

- `jobs.json` parsed successfully with `python3 -m json.tool`.
- `cronjob list` shows active ZeusOS jobs now preview as `ZeusOS ...`.
- Enabled jobs no longer matched `Jarvis`, `jinwang_jarvis`, or `queries/jinwang-jarvis` in the post-edit scan.

## Residuals

- `workdir=/home/jinwang/workspace/zeus-os` intentionally remains until repo-path collision is resolved.
- Some paused/historical jobs and cron output history may still contain legacy strings and are not canonical active surfaces.
