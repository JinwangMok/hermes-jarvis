# Minerva Discord gateway bridge

This document describes the ZeusOS-owned Hermes plugin bridge in `plugins/hermes_minerva_gateway/`.

## What it does

- Intercepts explicit Discord text commands `/minerva ...` through Hermes `pre_gateway_dispatch`.
- Default-delegates non-trivial Boramae Discord requests into Minerva when they are task-like or question-like; short acknowledgements/choice replies such as `A`, `ok`, `네`, and unrelated slash commands stay on the normal gateway path.
- Does not auto-delegate inside existing `Minerva · ...` task threads or from bot-authored messages, preventing nested Minerva thread loops.
- Creates a sibling Discord task thread under the parent channel, even when invoked from an existing thread.
- Starts a ZeusOS Minerva run with `origin_channel_id=<parent channel>` and `origin_thread_id=<new task thread>`.
- Renders the latest `discord_cards.jsonl` record as a Discord message with proposal option buttons when an interview dimension is unresolved.
- Routes button clicks through `MinervaWorkflow.handle_interaction()` so stale/mismatched interactions are rejected by ZeusOS state rules.

## Boundary

- Hermes source remains untouched.
- The plugin is stored in the ZeusOS repo and is intended to be symlinked/enabled in `~/.hermes/plugins` only with operator approval.
- The gateway must still be restarted before newly enabled plugin code becomes active.
- Buttons created by this initial bridge are process-local `discord.py` views; restart-safe persistent component dispatch is a later hardening step.

## Activation checklist

Only do this with operator approval because it changes Hermes runtime configuration and needs a gateway restart.

1. Symlink/copy plugin into Hermes user plugins, e.g.
   `~/.hermes/plugins/hermes_minerva_gateway -> /home/jinwang/workspace/zeus-os/plugins/hermes_minerva_gateway`.
2. Enable plugin key/name `hermes-minerva-gateway` in Hermes config (`plugins.enabled`).
3. Restart gateway using the established Jinwang/Boramae restart handoff procedure.
4. Smoke test in Discord: `/minerva <small goal>` and one non-trivial normal Boramae request such as `이 설계를 검증하고 보고해줘`.
5. Verify a sibling thread appears, a Minerva card is posted, normal simple replies like `A` are not auto-delegated, and button clicks produce an ephemeral acceptance/rejection message.

Runtime activation is an operator-state check, not a repository fact: verify `~/.hermes/plugins/hermes_minerva_gateway`, `plugins.enabled`, and gateway restart status on the live machine before claiming `/minerva` is active.

## Known caveat

This bridge makes real Discord buttons for newly posted Minerva cards, but callbacks are not yet restart-persistent. If the gateway restarts, old button messages may not have active callbacks; starting a fresh Minerva run or reposting the latest card is the safe recovery path until persistent interaction registration is added.

The ZeusOS card contract stores button definitions at `card.components`. Gateway code must render that nested field, including the three `select_proposal` buttons and the `other_opinion` button for unresolved dimensions, and pass `disabled` through to `discord.ui.Button`; otherwise the live message can appear without actionable controls even though `discord_cards.jsonl` is correct.
