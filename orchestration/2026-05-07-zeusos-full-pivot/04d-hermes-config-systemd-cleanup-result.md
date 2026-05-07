# Stage 4D Hermes Config/Systemd Cleanup Result

## Scope

Cleaned live user-systemd ZeusOS surfaces that could safely be handled before repo-path cutover. Hermes config path rewrites were deliberately deferred because `/home/jinwang/workspace/zeus-os` is already occupied by runtime data and is not yet the git worktree.

## Applied systemd changes

- Disabled legacy timers/services if present:
  - `jinwang-jarvis-cycle.*`
  - `jinwang-jarvis-weekly-review.*`
  - `jinwang-jarvis-hermes-health.*`
- Moved legacy disabled user-unit files out of the active unit directory to:
  - `/home/jinwang/.config/systemd/archive/zeusos-legacy-disabled-*`
- Replaced stale `zeus-os-cycle.*` and `zeus-os-weekly-review.*` user-unit files that pointed at pytest temp directories with repo template units.
- Kept `zeus-os-cycle.timer` and `zeus-os-weekly-review.timer` disabled to avoid duplicate scheduling with Hermes cron.
- Ran `systemctl --user daemon-reload`.

## Verification

- Active user-unit directory no longer has legacy filename refs.
- Active user-unit directory no longer has `pytest-of-jinwang` stale path refs.
- `hermes-gateway.service` remained active.
- `zeus-os-hermes-health.timer` remained active.

## Deferred residuals

The following are intentionally deferred to Stage 4E repo-path/data collision resolution:

- Active systemd `WorkingDirectory=/home/jinwang/workspace/zeus-os` and `cd /home/jinwang/workspace/zeus-os`.
- Hermes config paths under `/home/jinwang/.hermes/config.yaml` for external skill/STT commands.

Reason: changing those now would point live automation at `/home/jinwang/workspace/zeus-os`, which currently contains runtime data/state and is not the git worktree.
