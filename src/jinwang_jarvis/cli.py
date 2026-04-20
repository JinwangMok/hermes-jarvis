from __future__ import annotations

import argparse
import json
from typing import Sequence

from .backfill import run_next_backfill_step, run_progressive_backfill
from .bootstrap import bootstrap_workspace
from .briefing import generate_briefing
from .calendar import build_fake_calendar_runner, collect_calendar_snapshots
from .classifier import classify_messages
from .config import load_pipeline_config
from .digest import generate_digest
from .feedback import record_proposal_feedback
from .intelligence import collect_knowledge_mail, generate_daily_intelligence_report
from .knowledge import synthesize_knowledge
from .mail import build_fake_mail_runner, collect_mail_snapshots
from .proposals import generate_proposals
from .review import generate_weekly_review
from .runtime import install_systemd_user_units, run_pipeline_cycle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jinwang-jarvis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap", help="Initialize workspace directories and SQLite schema")
    bootstrap_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    collect_mail_parser = subparsers.add_parser("collect-mail", help="Collect inbox and sent mail snapshots")
    collect_mail_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    collect_mail_parser.add_argument("--runner", choices=("real", "fake"), default="real", help="Use real Himalaya commands or a deterministic fake runner for tests")

    collect_knowledge_parser = subparsers.add_parser("collect-knowledge-mail", help="Collect All Mail/archive knowledge-lane messages into the separate intelligence store")
    collect_knowledge_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    collect_knowledge_parser.add_argument("--months", type=int, default=36, help="Historical window depth in months")

    collect_calendar_parser = subparsers.add_parser("collect-calendar", help="Collect Google Calendar snapshots")
    collect_calendar_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    collect_calendar_parser.add_argument("--runner", choices=("real", "fake"), default="real", help="Use real gws commands or a deterministic fake runner for tests")

    classify_parser = subparsers.add_parser("classify-messages", help="Resolve sender identities and classify collected mail")
    classify_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    cycle_parser = subparsers.add_parser("run-cycle", help="Run one full polling cycle: mail, calendar, classification, proposals, digest")
    cycle_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    proposal_parser = subparsers.add_parser("generate-proposals", help="Generate recommendation-only proposals and a digest artifact")
    proposal_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    digest_parser = subparsers.add_parser("generate-digest", help="Generate a markdown digest from current pipeline state")
    digest_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    briefing_parser = subparsers.add_parser("generate-briefing", help="Generate a natural-language Jarvis briefing artifact for Discord delivery")
    briefing_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    knowledge_parser = subparsers.add_parser("synthesize-knowledge", help="Generate a rolling watchlist and optional wiki synthesis from the latest proposal artifact")
    knowledge_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    knowledge_parser.add_argument("--no-write-wiki", action="store_true", help="Only write watchlist artifact/DB state; skip wiki update")

    intelligence_parser = subparsers.add_parser("generate-daily-intelligence", help="Generate a category-based daily intelligence report and wiki notes from the knowledge lane")
    intelligence_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    intelligence_parser.add_argument("--lookback-days", type=int, default=7, help="How many recent days to summarize")

    feedback_parser = subparsers.add_parser("record-feedback", help="Record allow/reject feedback for a proposal")
    feedback_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    feedback_parser.add_argument("--proposal-id", required=True, help="Proposal identifier")
    feedback_parser.add_argument("--decision", required=True, choices=("allow", "reject"), help="User decision")
    feedback_parser.add_argument("--reason-code", required=True, help="Reason code for the decision")
    feedback_parser.add_argument("--note", default=None, help="Optional freeform note")
    feedback_parser.add_argument("--create-calendar", action="store_true", help="When decision=allow, immediately create the calendar event via Google Workspace")

    review_parser = subparsers.add_parser("weekly-review", help="Generate a weekly review markdown artifact")
    review_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    backfill_parser = subparsers.add_parser("backfill", help="Record progressive backfill windows")
    backfill_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    backfill_parser.add_argument("--windows", default="1w,1m,3m,6m", help="Comma-separated backfill windows")

    backfill_next_parser = subparsers.add_parser("backfill-next", help="Extend historical coverage by only the next 3-month slice (6m→9m→12m...)" )
    backfill_next_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    backfill_next_parser.add_argument("--max-months", type=int, default=36, help="Stop staged extension once this month depth is reached")

    install_parser = subparsers.add_parser("install-systemd", help="Install and enable systemd user timers for automatic polling and weekly review")
    install_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    install_parser.add_argument("--poll-minutes", type=int, default=5, help="Polling interval in minutes")
    install_parser.add_argument("--no-enable", action="store_true", help="Only write units and daemon-reload; do not enable timers")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "bootstrap":
        config = load_pipeline_config(args.config)
        bootstrap_workspace(config)
        return 0

    if args.command == "collect-mail":
        config = load_pipeline_config(args.config)
        runner = build_fake_mail_runner(config.accounts) if args.runner == "fake" else None
        result = collect_mail_snapshots(config, runner=runner)
        print(json.dumps({
            "snapshot_file": str(result["snapshot_file"]),
            "accounts": result["accounts"],
            "total_messages": result["total_messages"],
        }, ensure_ascii=False))
        return 0

    if args.command == "collect-knowledge-mail":
        config = load_pipeline_config(args.config)
        result = collect_knowledge_mail(config, months=args.months)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "collect-calendar":
        config = load_pipeline_config(args.config)
        runner = build_fake_calendar_runner() if args.runner == "fake" else None
        result = collect_calendar_snapshots(config, runner=runner)
        print(json.dumps({
            "snapshot_file": str(result["snapshot_file"]),
            "calendar_id": result["calendar_id"],
            "event_count": result["event_count"],
        }, ensure_ascii=False))
        return 0

    if args.command == "classify-messages":
        config = load_pipeline_config(args.config)
        result = classify_messages(config)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "run-cycle":
        config = load_pipeline_config(args.config)
        result = run_pipeline_cycle(config)
        print(json.dumps({
            "mail_messages": result["mail"]["total_messages"],
            "calendar_events": result["calendar"]["event_count"],
            "classified_messages": result["classification"]["message_count"],
            "proposal_count": result["proposals"]["proposal_count"],
            "digest_path": str(result["digest"]["artifact_path"]),
        }, ensure_ascii=False))
        return 0

    if args.command == "generate-proposals":
        config = load_pipeline_config(args.config)
        proposal_result = generate_proposals(config)
        knowledge_result = synthesize_knowledge(config, write_wiki=True)
        digest_result = generate_digest(config, proposal_result)
        print(json.dumps({
            **proposal_result,
            "artifact_path": str(proposal_result["artifact_path"]),
            "digest_path": str(digest_result["artifact_path"]),
            "watchlist_path": str(knowledge_result["artifact_path"]),
            "watchlist_count": knowledge_result["watchlist_count"],
            "wiki_page_path": str(knowledge_result["wiki_page_path"]) if knowledge_result.get("wiki_page_path") else None,
            "memory_index_path": str(knowledge_result["memory_note_paths"].get("index")) if knowledge_result.get("memory_note_paths") else None,
        }, ensure_ascii=False))
        return 0

    if args.command == "generate-digest":
        config = load_pipeline_config(args.config)
        result = generate_digest(config)
        print(json.dumps({**result, "artifact_path": str(result["artifact_path"])}, ensure_ascii=False))
        return 0

    if args.command == "generate-briefing":
        config = load_pipeline_config(args.config)
        result = generate_briefing(config)
        print(json.dumps({**result, "artifact_path": str(result["artifact_path"])}, ensure_ascii=False))
        return 0

    if args.command == "synthesize-knowledge":
        config = load_pipeline_config(args.config)
        result = synthesize_knowledge(config, write_wiki=not args.no_write_wiki)
        print(json.dumps({
            **result,
            "artifact_path": str(result["artifact_path"]),
            "proposal_artifact_path": str(result["proposal_artifact_path"]),
            "wiki_page_path": str(result["wiki_page_path"]) if result.get("wiki_page_path") else None,
            "memory_index_path": str(result["memory_note_paths"].get("index")) if result.get("memory_note_paths") else None,
            "memory_note_paths": {key: str(value) for key, value in (result.get("memory_note_paths") or {}).items()},
        }, ensure_ascii=False))
        return 0

    if args.command == "generate-daily-intelligence":
        config = load_pipeline_config(args.config)
        result = generate_daily_intelligence_report(config, lookback_days=args.lookback_days)
        print(json.dumps({
            **result,
            "artifact_path": str(result["artifact_path"]),
            "wiki_note_path": str(result["wiki_note_path"]),
            "index_path": str(result["index_path"]),
        }, ensure_ascii=False))
        return 0

    if args.command == "record-feedback":
        config = load_pipeline_config(args.config)
        result = record_proposal_feedback(
            config,
            proposal_id=args.proposal_id,
            decision=args.decision,
            reason_code=args.reason_code,
            freeform_note=args.note,
            create_calendar_event=args.create_calendar,
        )
        briefing_result = generate_briefing(config)
        print(json.dumps({
            **result,
            "artifact_path": str(result["artifact_path"]),
            "next_briefing_path": str(briefing_result["artifact_path"]),
            "next_pending_approval_count": briefing_result["pending_approval_count"],
            "next_open_proposal_count": briefing_result["open_proposal_count"],
            "next_briefing_text": briefing_result["message_text"],
        }, ensure_ascii=False))
        return 0

    if args.command == "weekly-review":
        config = load_pipeline_config(args.config)
        result = generate_weekly_review(config)
        print(json.dumps({**result, "artifact_path": str(result["artifact_path"])}, ensure_ascii=False))
        return 0

    if args.command == "backfill":
        config = load_pipeline_config(args.config)
        windows = tuple(part.strip() for part in args.windows.split(",") if part.strip())
        result = run_progressive_backfill(config, windows=windows)
        print(json.dumps({
            "completed_at": result["completed_at"],
            "windows": [run["window_name"] for run in result["runs"]],
            "artifacts": [str(run["artifact_path"]) for run in result["runs"]],
        }, ensure_ascii=False))
        return 0

    if args.command == "backfill-next":
        config = load_pipeline_config(args.config)
        result = run_next_backfill_step(config, max_months=args.max_months)
        print(json.dumps({
            "completed_at": result["completed_at"],
            "executed": result["executed"],
            "next_window": result["next_window"],
            "windows": [run["window_name"] for run in result["runs"]],
            "artifacts": [str(run["artifact_path"]) for run in result["runs"]],
            "completed_windows": result["completed_windows"],
        }, ensure_ascii=False))
        return 0

    if args.command == "install-systemd":
        config = load_pipeline_config(args.config)
        result = install_systemd_user_units(config, poll_minutes=args.poll_minutes, enable=not args.no_enable)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
