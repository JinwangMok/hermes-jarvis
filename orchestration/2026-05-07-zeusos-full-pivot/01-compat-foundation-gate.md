# Stage 1 Gate — ZeusOS Compatibility Foundation

## Scope

Allowed:
- Add canonical `zeus_os` import facade.
- Add `python -m zeus_os.cli` with canonical program name `zeus-os`.
- Preserve `jinwang_jarvis` and `python -m jinwang_jarvis.cli` as legacy compatibility.
- Add tests for old/new CLI coexistence.

Not allowed in this stage:
- repo path rename
- package distribution rename
- cron/systemd/gateway mutation
- wiki/memory rewrite
- removal of legacy `jinwang_jarvis`

## Local implementation evidence

Changed/added:
- `pyproject.toml` — adds console scripts `zeus-os` and `jinwang-jarvis`.
- `src/jinwang_jarvis/cli.py` — parser/main now accept `prog`, defaulting to `jinwang-jarvis`.
- `src/zeus_os/__init__.py` — canonical facade aliases legacy top-level modules and current `jinwang_jarvis.zeus_os` control-plane modules.
- `src/zeus_os/cli.py` — canonical CLI wrapper invoking legacy implementation with `prog="zeus-os"`.
- `tests/test_zeus_os_facade.py` — import and CLI coexistence tests.

## Verification

Commands:

```bash
python -m pytest tests/test_zeus_os_facade.py tests/test_zeus_cli.py -q
# 18 passed

PYTHONPATH=src python -m pytest \
  tests/test_zeus_os_facade.py \
  tests/test_zeus_cli.py \
  tests/test_zeus_worker.py \
  tests/test_zeus_adapters.py -q
# 29 passed
```

Verified behavior:
- `python -m zeus_os.cli --help` shows `usage: zeus-os`.
- `python -m jinwang_jarvis.cli --help` still shows `usage: jinwang-jarvis`.
- `zeus_os.queue/schema/worker` alias existing `jinwang_jarvis.zeus_os.*` modules.

## External/MoA review

- Contractor re-review: **96/100 PASS**.
- Adversarial side-effect re-review: **95/100 PASS**.

Critical blockers: none.

Non-blocking risks:
- `zeus_os.__init__` eager aliasing is acceptable for Stage 1, but later native `zeus_os.*` modules must shrink/remove aliases deliberately.
- `zeus-os` console-script collision is possible in external environments; local Stage 1 packaging foundation accepts it.
- This does **not** claim Jarvis removal; it only creates a safe canonical foundation.

## Gate decision

**PASS — controller score 96/100.**

Next allowed stage: Stage 2 repo-local user-facing sweep, still without cron/systemd/gateway/wiki/memory live mutation.
