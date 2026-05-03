# HOOO live smoke + final cleanup reference

Use this when finishing a `/hooo`/Houroboros Discord bridge task after gateway/plugin enablement.

## Live smoke pattern

1. If the origin is already a Discord thread, create a **sibling** thread under the parent channel; do not bind the new run to the origin thread.
2. Start the run with the parent channel and source origin preserved:
   ```bash
   PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo start \
     --config config/pipeline.local.yaml \
     --goal "live smoke: ..." \
     --origin-platform discord \
     --origin-channel-id "$PARENT_CHANNEL_ID" \
     --origin-thread-id "$SOURCE_THREAD_ID" \
     --auto-open-thread \
     --thread-name "$THREAD_NAME"
   ```
3. Mark the created live thread:
   ```bash
   PYTHONPATH=src python3 -m jinwang_jarvis.cli hooo mark-thread-created \
     --config config/pipeline.local.yaml \
     --run-id "$RUN_ID" \
     --thread-id "$NEW_THREAD_ID" \
     --thread-name "$THREAD_NAME" \
     --message-id "$MESSAGE_ID" \
     --jump-url "$JUMP_URL"
   ```
4. Verify `discord_cards.jsonl`; extract a real `custom_id`; reduce it through `hooo interact`.
5. Add structured turns for `Scope:`, `Acceptance:`, `Constraint:`, `Executor:`, and `Permission:`. Then run `hooo seed` and confirm `seed_ready=true`, low ambiguity, and phase `seeded`.
6. Post a concise smoke result to the sibling thread and fetch it back through Discord API/tooling.

## Caveat language

Say explicitly: live smoke validates Discord thread side effect plus Jarvis card/reducer/seed path. A physical human Discord UI button click is separate if the available tooling cannot impersonate a user click. Do not overclaim deterministic placeholder execution as real task completion.

## Post-task verification

Run at least:

```bash
PYTHONPATH=src python -m compileall -q src/jinwang_jarvis plugins/hermes_hooo_gateway tests/test_houroboros.py tests/test_hooo_gateway_plugin.py
PYTHONPATH=src pytest -q tests/test_houroboros.py tests/test_hooo_gateway_plugin.py tests/test_hermes_skill_context.py tests/test_hermes_skill_search.py
PYTHONPATH=src pytest -q
```

Check gateway/config without restarting:

```bash
python3 - <<'PY'
from pathlib import Path
import os, yaml
cfg=yaml.safe_load(Path('/home/jinwang/.hermes/config.yaml').read_text())
print('approvals.mode=', cfg.get('approvals',{}).get('mode'))
print('plugins=', cfg.get('plugins'))
print('hooo_link=', os.path.realpath(Path.home()/'.hermes/plugins/hermes_hooo_gateway'))
PY
systemctl --user is-active hermes-gateway.service
systemctl --user show hermes-gateway.service -p ActiveState -p SubState -p MainPID -p NRestarts -p ActiveEnterTimestamp --no-pager
```

## Git cleanup pattern

When several workstreams are mixed, split commits by concern rather than making one giant checkpoint:

- Hermes skill retrieval sidecar: search/context modules, tests, fixture, related orchestration evidence.
- HOOO/Houroboros harness and Discord bridge: CLI/state machine/plugin/docs/tests/live-smoke evidence.
- Unrelated reader-facing report quality fixes: report generator/linter/tests.
- Safe restart bundle: recovery scripts, preflight snapshots, restart safety-belt skill changes.

After committing, re-run targeted HOOO/skill tests and confirm both Jarvis and safe-restart-bundle worktrees are clean.

## Post-restart continuation / final push closeout

If the gateway/session reset interrupts the finalization turn, resume from live state instead of trusting the last chat summary:

1. Re-read recent Discord messages and session summaries to recover the exact requested scope, especially mixed HOOO + watch-source / information-source work.
2. Inspect the live repo first:
   ```bash
   cd /home/jinwang/workspace/jinwang-jarvis
   git branch --show-current
   git status --short --branch
   git log --oneline -8 --decorate
   git remote -v
   git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true
   git diff --stat
   git ls-files --others --exclude-standard | sed -n '1,120p'
   ```
3. For Jinwang's Jarvis repo, verify both remotes when the intent was “commit/push”:
   - `origin` may already be up to date while `public` is still behind.
   - Push `public main` explicitly when `git status` says `main...public/main [ahead N]`.
   - Final invariant should be `HEAD = origin/main = public/main` and a clean worktree.
4. Re-run at least the relevant targeted tests, then the full Jarvis suite when the changes include workflow/runtime/report/source code:
   ```bash
   PYTHONPATH=src pytest -q tests/test_watch.py tests/test_hooo_gateway_plugin.py tests/test_houroboros.py
   PYTHONPATH=src pytest -q
   ```
5. Check gateway status without restarting unless a new runtime change truly requires it:
   ```bash
   systemctl --user show hermes-gateway.service -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
   ```
6. If `hermes-health-check` reports `missing DISCORD_BOT_TOKEN` from the shell, do not mislabel the gateway as broken. Cross-check gateway logs for `discord connected` / `Gateway running` markers; the service may have the token in its unit environment even when the current shell does not.
