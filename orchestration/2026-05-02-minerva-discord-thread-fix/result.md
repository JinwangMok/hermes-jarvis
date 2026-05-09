# Minerva Discord Thread Fix Result

Implemented and review-hardened the Jarvis-owned `/minerva` and `/minerva` workflow harness completion for the Discord-thread-first flow: Discord thread auto-open -> Interview -> Seed -> Execute -> Evaluate -> Evolve.

## Delivered

- Added a safe Discord thread adapter boundary in `src/jinwang_jarvis/minerva.py`.
  - `DiscordThreadClient` can be injected in tests or a future gateway.
  - Plain CLI mode uses `PendingDiscordThreadClient`, which writes deterministic `thread_handoff.json` instead of creating a real Discord thread.
  - Thread metadata is stored in `origin.json` and surfaced through `status` and `export`.
- Added CLI support in `src/jinwang_jarvis/cli.py`.
  - `start --auto-open-thread --thread-name ... --origin-message-id ...` requests a safe thread handoff.
  - `mark-thread-created` records a gateway-created Discord thread back into Jarvis.
  - Invalid phase transitions and sqlite integrity failures return deterministic nonzero JSON errors.
- Review hardening after independent code review:
  - DB run row is reserved before any injected live Discord adapter side effect.
  - Same-second/same-goal run ID collisions are avoided with bounded nonce retry.
  - Placeholder execution/evaluation limitations are explicit in status/docs/artifacts.
  - Added negative/blocked evaluation coverage.
- Fixed state machine integrity.
  - `run` before `seed`, `evaluate` before `run`, `evolve` before `evaluate`, and `seed -> evolve` are rejected.
- Expanded tests in `tests/test_minerva.py`.
  - Fake adapter creation, pending handoff, `/minerva` alias, `mark-thread-created`, status/export metadata, invalid transition errors, adapter ordering, run-id collision avoidance, and blocked evaluation are covered.
- Updated `docs/minerva-workflow.md`, `skills/minerva/SKILL.md`, and `skills/minerva/SKILL.md`.

## Hermes/Boramae handoff gap

No Hermes source, `~/.hermes`, systemd, cron, secrets, or external services were modified. The remaining external integration is for Hermes/Boramae to consume `thread_handoff.json` with `action: discord.create_thread`, perform the live Discord side effect in its own runtime, then call `minerva mark-thread-created` with the resulting thread metadata.

## Verification

Controller checks passed after review fixes:

- `PYTHONPATH=src pytest -q tests/test_minerva.py` -> `11 passed`
- `PYTHONPATH=src pytest -q tests/test_minerva.py tests/test_cli.py tests/test_bootstrap.py` -> `26 passed`
- `PYTHONPATH=src python -m compileall -q src/jinwang_jarvis tests/test_minerva.py` -> exit code `0`
- Manual isolated temp CLI smoke completed `start -> turn -> seed -> run -> evaluate -> evolve -> status` with pending thread handoff, `deterministic_placeholder` execution mode, and `placeholder_substring_match` evaluation mode.
- Static AST scan of modified Python files found no eval/exec/shell/subprocess/network call additions.
- Independent review initially found important issues; fixes were applied and targeted verification is green.
