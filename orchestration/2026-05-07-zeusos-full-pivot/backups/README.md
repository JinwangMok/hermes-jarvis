# Backup policy for this migration

Raw live Hermes config and cron snapshots were intentionally **not committed**.
They may contain private operational metadata. Rollback evidence is kept as
sanitized manifests/gate reports only; live rollback must use the current
operator-owned `~/.hermes/` state or external private backups.
