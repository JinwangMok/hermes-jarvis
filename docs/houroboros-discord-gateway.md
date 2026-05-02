# HOOO Discord gateway bridge

This document describes the Jarvis-owned Hermes plugin bridge in `plugins/hermes_hooo_gateway/`.

## What it does

- Intercepts Discord text commands `/hooo ...` and `/houroboros ...` through Hermes `pre_gateway_dispatch`.
- Creates a sibling Discord task thread under the parent channel, even when invoked from an existing thread.
- Starts a Jarvis HOOO run with `origin_channel_id=<parent channel>` and `origin_thread_id=<new task thread>`.
- Renders the latest `discord_cards.jsonl` record as a Discord message with buttons.
- Routes button clicks through `HouroborosWorkflow.handle_interaction()` so stale/mismatched interactions are rejected by Jarvis state rules.

## Boundary

- Hermes source remains untouched.
- The plugin is stored in the Jarvis repo and is intended to be symlinked/enabled in `~/.hermes/plugins` only with operator approval.
- The gateway must still be restarted before newly enabled plugin code becomes active.
- Buttons created by this initial bridge are process-local `discord.py` views; restart-safe persistent component dispatch is a later hardening step.

## Activation checklist

Only do this with operator approval because it changes Hermes runtime configuration and needs a gateway restart.

1. Symlink/copy plugin into Hermes user plugins, e.g.
   `~/.hermes/plugins/hermes_hooo_gateway -> /home/jinwang/workspace/jinwang-jarvis/plugins/hermes_hooo_gateway`.
2. Enable plugin key/name `hermes-hooo-gateway` in Hermes config (`plugins.enabled`).
3. Restart gateway using the established Jinwang/Boramae restart handoff procedure.
4. Smoke test in Discord: `/hooo <small goal>`.
5. Verify a sibling thread appears, a HOOO card is posted, and button clicks produce an ephemeral acceptance/rejection message.

Runtime activation is an operator-state check, not a repository fact: verify `~/.hermes/plugins/hermes_hooo_gateway`, `plugins.enabled`, and gateway restart status on the live machine before claiming `/hooo` is active.

## Known caveat

This bridge makes real Discord buttons for newly posted HOOO cards, but callbacks are not yet restart-persistent. If the gateway restarts, old button messages may not have active callbacks; starting a fresh HOOO run or reposting the latest card is the safe recovery path until persistent interaction registration is added.

The Jarvis card contract stores button definitions at `card.components`. Gateway code must render that nested field and pass `disabled` through to `discord.ui.Button`; otherwise the live message can appear without actionable controls even though `discord_cards.jsonl` is correct.
