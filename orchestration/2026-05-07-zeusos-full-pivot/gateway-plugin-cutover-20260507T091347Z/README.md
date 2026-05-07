# Gateway plugin cutover artifact policy

The raw `~/.hermes/config.yaml` before/after copies were removed before commit
because live Hermes config snapshots are not source artifacts.  The committed
`result.md` records only the sanitized cutover evidence: active gateway state and
the enabled plugin names.
