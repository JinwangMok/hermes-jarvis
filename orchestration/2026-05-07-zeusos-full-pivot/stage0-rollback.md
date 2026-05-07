# Stage 0 Rollback Notes — Sanitized

Created before live-facing ZeusOS cutover work.

## Repo rollback
- Safety tag: `pre-zeusos-full-pivot-20260507`
- Restore code state if needed:
  ```bash
  git -C /home/jinwang/workspace/zeus-os reset --hard pre-zeusos-full-pivot-20260507
  ```

## Hermes config rollback
- Raw `~/.hermes/config.yaml` backups were removed from repo artifacts before commit.
- Rollback must use current operator-owned `~/.hermes/config.yaml` history/private backup, not this git repo.
- For the Stage3 plugin cutover specifically, switch enabled plugin from `hermes-zeus-styled-voice-gateway` back to `hermes-jarvis-styled-voice-gateway` only if the Zeus plugin fails, then restart gateway with the recovery belt armed.

## Cron rollback
- Raw cron job snapshots were removed from repo artifacts before commit.
- Any cron rollback must be performed from Hermes-owned state or private backup.

## systemd rollback
- Repo templates are committed; live user unit writes/restarts require the Hermes gateway recovery safety belt.
- Legacy `jinwang-jarvis-*` health units should not be re-enabled together with `zeus-os-hermes-health.timer`; avoid duplicate restart-capable watchdogs.

## Private material
- `.env`, auth credential pools, raw config snapshots, and cron snapshots are intentionally not committed.
