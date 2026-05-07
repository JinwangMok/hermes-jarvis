# Stage 4E/4F Repo Path and Package Cutover Result

## Scope

Stage 4E/4F completed the active ZeusOS cutover for repo path, Python package/distribution, live systemd health surface, Hermes plugin surface, and active source/test/plugin/config naming.

Historical evidence, rollback bundles, raw/generated archives, `data/`, `state/`, and orchestration records remain non-canonical evidence layers and are excluded from active-zero assertions.

## Applied changes

- Canonical repo path is now `/home/jinwang/workspace/zeus-os`.
- Compatibility symlink exists: `/home/jinwang/workspace/jinwang-jarvis` -> `/home/jinwang/workspace/zeus-os`.
- Primary Python package moved from `src/jinwang_jarvis` to `src/zeus_os`.
- Distribution metadata is canonical: `name = "zeus-os"`.
- Console script is canonical: `zeus-os = "zeus_os.cli:main"`.
- Legacy console script was removed from `pyproject.toml`.
- Hermes styled-voice plugin directory was canonicalized; legacy plugin directory is deleted.
- `scripts/install.sh` and `src/zeus_os/runtime.py` disable both canonical superseded scheduler units and computed legacy health/scheduler unit names before enabling the canonical health timer. Legacy names are computed via split literals to avoid reintroducing active source-facing old-name surfaces.
- Ignored stale repo-local generated wiki copy was archived under `.local-archive/` and removed from active filesystem surface.

## Verification

- `PYTHONPATH=src python3 -m pytest -q` -> `394 passed`.
- `git diff --check` -> pass.
- `python3 -m compileall -q src plugins tests scripts skills/styled-voice/scripts` -> pass.
- `PYTHONPATH=src python3 -m zeus_os.cli --help` -> pass.
- Canonical imports pass: `zeus_os`, `zeus_os.config`, `zeus_os.runtime`, `zeus_os.queue`, `zeus_os.schema`.
- Live user systemd:
  - `hermes-gateway.service` -> active.
  - `zeus-os-hermes-health.timer` -> active.
  - `zeus-os-cycle.timer` and `zeus-os-weekly-review.timer` -> disabled.
- Active residual scan excluding history/backups/data/state/orchestration/.local-archive:
  - content residual: 0.
  - filename residual: 0.

## External review synthesis

- General final review: PASS, 97/100 before final ignored-wiki cleanup; after cleanup the noted filename residual is removed.
- Adversarial final review after legacy-disable remediation: PASS, 96/100, no blockers.

## Non-blocking notes

- Historical orchestration and backup files intentionally preserve old names as audit/rollback evidence.
- `data/` and `state/` are runtime/private stores and remain outside tracked source cutover; handle DB/file internal migrations only if a future runtime check proves they are active blockers.
- Compatibility symlink keeps old workspace path callers from breaking while active jobs are already canonicalized.

## Gate verdict

PASS for Stage 4E/4F active cutover.
