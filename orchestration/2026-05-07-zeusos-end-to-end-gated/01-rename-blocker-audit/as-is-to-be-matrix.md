# Phase 1.0 AS-IS → TO-BE Matrix

**Scope:** read-only rename-blocker audit. This matrix is the mechanical checkpoint before any code cleanup, alias, profile split, systemd change, wiki movement, or live adapter work.

| Surface | AS-IS evidence | TO-BE target | Next safe action | Gate before mutation |
|---|---|---|---|---|
| Product identity | README/docs say ZeusOS product/control-plane; repo/import/systemd still `jinwang-jarvis`/`jinwang_jarvis` | ZeusOS identity documented while compatibility names remain operational | Keep docs stance; no rename | `repo_write` only for docs; no runtime rename |
| Zeus runtime foundation | `src/jinwang_jarvis/zeus_os/*`; `tests/test_zeus_*.py`; 79 tests pass | Treat as existing foundation; harden rather than recreate | Add tests/cleanup only after Phase 1.0 gate | `repo_write`; tests must pass |
| CLI parser | `src/jinwang_jarvis/cli.py` has local `build_zeus_parser(zeus_subparsers)` while `src/jinwang_jarvis/zeus_os/cli.py` has standalone `build_zeus_parser()` | Single source of truth or parity test preventing drift | Phase 1.1 parser dedupe/parity tests | `repo_write`; old `python -m jinwang_jarvis.cli zeus ...` unchanged |
| Absolute workspace paths | `tests/test_config.py`, systemd units, local config, cron workdirs reference `/home/jinwang/workspace/jinwang-jarvis` | Runtime code/config stays workspace-root driven; live automation paths migrate only later | Phase 1.2 source/test cleanup for non-live assumptions only | systemd/cron untouched until automation gate |
| Styled voice samples | `src/jinwang_jarvis/styled_voice_samples.py` defaults to `~/workspace/jinwang-jarvis/data/styled-voice-samples` | Default resolves from config/workspace root or explicit CLI library dir | Phase 1.3 config-driven sample path | `repo_write`; no gateway/plugin restart |
| Wiki generated paths | `queries/jinwang-jarvis-*` constants and tests exist | Generated paths remain compatibility surface until writer migration | Inventory only; no wiki path move | wiki write/migration explicit approval; no `raw/` rewrite |
| Systemd units | active `jinwang-jarvis-hermes-health.timer`; `hermes-gateway.service` active; unit files embed repo path | No live unit rename in Phase 1; future migration requires backup/rollback | Read-only inventory only | `gateway_systemd` + recovery plan |
| Hermes cron jobs | 7 jobs reference Jarvis workdir; several enabled | Cron workdir remains as-is | Inventory only | cron/update approval; no job mutation |
| Hermes plugins | `hermes_minerva_gateway`, `hermes_jarvis_styled_voice_gateway` symlinks exist | Plugins treated as compatibility projections/adapters | Inventory only | `gateway_systemd` for live plugin change |
| External repos/K-Skill/browser helpers | Docs say adapters, no vendoring; browser recipe stance is documented only | Adapter manifests + recipe registry later, dry-run first | Defer to adapter phase after Phase 1 cleanup | `external_repo_write` forbidden without explicit approval |
| Canonical state | SQLite + registered filesystem artifacts in Zeus docs/runtime | Preserve canonical/projection split | No DB migration in Phase 1 | `local_db_write` only in test temp dirs; live migration blocked |
| Projections | Discord/Markdown/A2A/wiki reports are projections | Render/dry-run only until approval | No live post | `external_post`/`credential_access` gates |

## Controller conclusion

Phase 1.0 closes the missing mechanical AS-IS → TO-BE gap. It **does not authorize** implementation beyond the next narrow cleanup substage. The first code substage, if allowed, should be CLI parser drift/parity because it is local, testable, and does not touch live automation.
