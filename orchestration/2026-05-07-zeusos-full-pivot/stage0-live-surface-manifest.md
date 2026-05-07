# Stage 0 Live Surface Manifest — Sanitized

Generated for the ZeusOS full-pivot gate. Raw command transcripts and live config snapshots were removed before commit.

## Repo
- Worktree: `/home/jinwang/workspace/zeus-os`
- Branch during migration: `main`
- Safety tag created locally: `pre-zeusos-full-pivot-20260507`

## Live surfaces considered
- Hermes config: `~/.hermes/config.yaml` — inspected, not committed.
- Hermes plugins: `~/.hermes/plugins` — active styled-voice plugin cut over to `hermes-zeus-styled-voice-gateway`.
- Hermes gateway: `hermes-gateway.service` — restarted with recovery belt armed; verified active after cutover.
- User systemd timers/services: legacy `jinwang-jarvis-*` health/cycle/weekly and canonical `zeus-os-*` health/cycle/weekly were inventoried.
- Cron jobs: inventoried separately; raw cron snapshot was not committed.
- Wiki: policies read; no raw wiki rewrite in this stage.

## Commit boundary
- Commit sanitized gate reports, code, tests, repo templates, and plugin source.
- Do not commit raw live config, `.env`, auth files, cron snapshots, or unredacted journal dumps.
