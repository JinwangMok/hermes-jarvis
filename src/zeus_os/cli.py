from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Sequence

from .backfill import run_next_backfill_step, run_progressive_backfill
from .bootstrap import bootstrap_workspace
from .briefing import generate_briefing
from .calendar import build_fake_calendar_runner, collect_calendar_snapshots
from .classifier import classify_messages
from .config import load_pipeline_config
from .digest import generate_digest
from .feedback import record_proposal_feedback
from .hermes_continuity import check_hermes_customizations
from .hermes_skill_context import generate_skill_context
from .hermes_skill_lifecycle import audit_hermes_skill_lifecycle, record_skill_telemetry
from .houroboros import HouroborosWorkflow
from .hermes_skill_search import DEFAULT_SKILL_SEARCH_DB, build_skill_search_index, evaluate_skill_search, search_skills
from .intelligence import collect_knowledge_mail, generate_daily_intelligence_report
from .knowledge import synthesize_knowledge
from .mail import build_fake_mail_runner, collect_mail_snapshots
from .news_center import append_news_center_to_daily_report, collect_news_center, generate_podcast_script
from .personal_radar import generate_personal_radar_coverage_verification, generate_personal_radar_source_audit
from .proposals import generate_proposals
from .review import generate_weekly_review
from .runtime import check_hermes_zeusos_health, install_hermes_standby_units, install_systemd_user_units, run_pipeline_cycle
from .styled_voice_samples import add_samples as add_styled_voice_samples
from .styled_voice_samples import collect_profile_audio, init_library as init_styled_voice_library, list_profiles as list_styled_voice_profiles, profile_dir as styled_voice_profile_dir
from .unified_daily_report import generate_unified_daily_report
from .watch import build_watch_stories, collect_watch_signals, generate_external_hot_issue_alert, generate_watch_report, judge_watch_issues, run_watch_cycle, sync_watch_sources
from .wiki_search import rebuild_operational_search_index, search_operational_index
from .wiki_semantic_lint import lint_wiki_semantics
from .zeus_os.cli import handle_zeus, populate_zeus_subparsers


def build_parser(prog: str = "zeus-os") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
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

    briefing_parser = subparsers.add_parser("generate-briefing", help="Generate a natural-language ZeusOS briefing artifact for Discord delivery")
    briefing_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    knowledge_parser = subparsers.add_parser("synthesize-knowledge", help="Generate a rolling watchlist and optional wiki synthesis from the latest proposal artifact")
    knowledge_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    knowledge_parser.add_argument("--no-write-wiki", action="store_true", help="Only write watchlist artifact/DB state; skip wiki update")

    wiki_search_index_parser = subparsers.add_parser("wiki-search-index", help="Rebuild operational wiki/search FTS sidecar tables")
    wiki_search_index_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    wiki_search_parser = subparsers.add_parser("wiki-search", help="Search operational ZeusOS FTS sidecar tables")
    wiki_search_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    wiki_search_parser.add_argument("--query", required=True, help="FTS search query")
    wiki_search_parser.add_argument("--limit", type=int, default=10, help="Maximum result rows")

    wiki_semantic_lint_parser = subparsers.add_parser("wiki-semantic-lint", help="Read-only semantic lint for generated/canonical wiki boundaries")
    wiki_semantic_lint_parser.add_argument("--config", default="", help="Path to pipeline.yaml")
    wiki_semantic_lint_parser.add_argument("--wiki-root", default="", help="Wiki root; overrides --config wiki_root")

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

    sync_watch_parser = subparsers.add_parser("sync-watch-sources", help="Load watch source YAML definitions and sync them into SQLite")
    sync_watch_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    collect_watch_parser = subparsers.add_parser("collect-watch-signals", help="Collect raw watch signals from enabled watch sources")
    collect_watch_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    build_watch_parser = subparsers.add_parser("build-watch-stories", help="Group collected signals into issue stories")
    build_watch_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    judge_watch_parser = subparsers.add_parser("judge-watch-issues", help="Judge watch issue importance and momentum")
    judge_watch_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    watch_report_parser = subparsers.add_parser("generate-watch-report", help="Generate a watch report artifact")
    watch_report_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    watch_report_parser.add_argument("--report-kind", default="hourly-hot-issues", help="Report kind")

    hot_alert_parser = subparsers.add_parser("generate-external-hot-issue-alert", help="Dedupe a watch report against external hot issue state and print the deliverable alert text")
    hot_alert_parser.add_argument("--report-path", required=True, help="Path to generated watch report markdown")
    hot_alert_parser.add_argument("--state-path", default="state/external_hot_issue_state.json", help="Path to external hot issue dedupe state JSON")

    radar_audit_parser = subparsers.add_parser("generate-personal-radar-source-audit", help="Generate a Personal Intelligence Radar source registry audit artifact")
    radar_audit_parser.add_argument("--registry-dir", default="config/personal-radar", help="Directory containing personal radar YAML registry files")
    radar_audit_parser.add_argument("--output-dir", default="data/personal-radar", help="Directory for generated audit artifacts")

    radar_verify_parser = subparsers.add_parser("verify-personal-radar-coverage", help="Verify Personal Opportunity Radar coverage gates for critical sources/items")
    radar_verify_parser.add_argument("--registry-dir", default="config/personal-radar", help="Directory containing personal radar YAML registry files")
    radar_verify_parser.add_argument("--output-dir", default="data/personal-radar", help="Directory for generated verification artifacts")
    radar_verify_parser.add_argument("--no-live", action="store_true", help="Skip live HTTP probes and only validate registry coverage")

    news_center_parser = subparsers.add_parser("generate-news-center", help="Collect Naver/Google News category briefs and write wiki shards")
    news_center_parser.add_argument("--taxonomy", default="config/personal-radar/naver-news-taxonomy.yaml", help="News taxonomy YAML")
    news_center_parser.add_argument("--output-dir", default="data/news-center", help="Directory for news-center artifacts")
    news_center_parser.add_argument("--wiki-root", default="", help="Wiki root; defaults to pipeline config wiki_root when --config is provided, otherwise ~/wiki")
    news_center_parser.add_argument("--config", default="", help="Optional pipeline config for wiki/workspace defaults")
    news_center_parser.add_argument("--per-source-limit", type=int, default=5, help="Maximum items per provider/query")

    append_news_parser = subparsers.add_parser("append-news-center-to-daily-report", help="Append or replace the news section in a daily hot-issues markdown report")
    append_news_parser.add_argument("--daily-report", required=True, help="Daily hot-issues markdown path")
    append_news_parser.add_argument("--news-markdown", required=True, help="News center markdown path")

    unified_daily_parser = subparsers.add_parser("generate-unified-daily-report", help="Generate the deterministic unified daily hot-issues report")
    unified_daily_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    unified_daily_parser.add_argument("--date", required=True, help="Report date YYYY-MM-DD")
    unified_daily_parser.add_argument("--hot-issue", default="", help="Optional existing hot-issues/watch markdown artifact")
    unified_daily_parser.add_argument("--news-json", default="", help="Optional news-center JSON artifact; defaults to data/news-center/latest.json")
    unified_daily_parser.add_argument("--opportunity-json", default="", help="Optional personal opportunity candidate JSON artifact")
    unified_daily_parser.set_defaults(delivery_gate=True)
    unified_daily_parser.add_argument("--delivery-gate", dest="delivery_gate", action="store_true", help="Run the hard Daily Hot Issues markdown→PDF delivery gate before returning success (default)")
    unified_daily_parser.add_argument("--skip-delivery-gate", dest="delivery_gate", action="store_false", help="Local debugging only: write the markdown target without the post-render reader-facing PDF gate")

    podcast_parser = subparsers.add_parser("generate-podcast-script", help="Generate a conversational TTS podcast script from a daily report")
    podcast_parser.add_argument("--daily-report", required=True, help="Daily hot-issues markdown path")
    podcast_parser.add_argument("--output-path", required=True, help="Output markdown/text script path")
    podcast_parser.add_argument("--max-items", type=int, default=8, help="Maximum issue/news cards to include")

    watch_cycle_parser = subparsers.add_parser("run-watch-cycle", help="Run one full watch cycle")
    watch_cycle_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")

    install_parser = subparsers.add_parser("install-systemd", help="Install and enable systemd user timers for automatic polling and weekly review")
    install_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    install_parser.add_argument("--poll-minutes", type=int, default=5, help="Polling interval in minutes")
    install_parser.add_argument("--no-enable", action="store_true", help="Only write units and daemon-reload; do not enable timers")

    standby_parser = subparsers.add_parser("install-standby-systemd", help="Write/install Hermes+ZeusOS always-on standby units and health-check timer")
    standby_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    standby_parser.add_argument("--health-minutes", type=int, default=5, help="Health-check interval in minutes")
    standby_parser.add_argument("--stale-minutes", type=int, default=15, help="Alert when an enabled Hermes cron job is this many minutes overdue")
    standby_parser.add_argument("--discord-channel", default="", help="Discord channel ID for health alerts; defaults to hermes.deliver_channel if it is discord:<id>")
    standby_parser.add_argument("--no-enable", action="store_true", help="Only write units and daemon-reload; do not enable health timer")
    standby_parser.add_argument("--workspace-only", action="store_true", help="Only render units under the repo systemd/ directory; do not touch ~/.config/systemd/user")
    standby_parser.add_argument("--install-gateway", action="store_true", help="Also install the repo-rendered hermes-gateway.service with Restart=always")

    health_parser = subparsers.add_parser("hermes-health-check", help="Check Hermes gateway + ZeusOS cron health and optionally alert Discord")
    health_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    health_parser.add_argument("--stale-minutes", type=int, default=15, help="Alert when an enabled Hermes cron job is this many minutes overdue")
    health_parser.add_argument("--discord-alert", action="store_true", help="Send Discord alert when health issues are detected")
    health_parser.add_argument("--discord-channel", default="", help="Discord channel ID for health alerts")
    health_parser.add_argument("--restart", action="store_true", help="Restart hermes-gateway.service if it is inactive, failed, or not Discord-ready")
    health_parser.add_argument("--readiness-timeout-seconds", type=int, default=45, help="Wait this long for Discord gateway readiness before alerting/restarting")
    health_parser.add_argument("--skip-discord-api-check", action="store_true", help="Skip the non-mutating Discord bot identity API check")

    customization_parser = subparsers.add_parser("hermes-customization-check", help="Passively inspect the Hermes agent + zeus-os customization contract")
    customization_parser.add_argument("--hermes-home", default=str(Path.home() / ".hermes"), help="Hermes home directory")
    customization_parser.add_argument("--hermes-agent-dir", default=str(Path.home() / ".hermes/hermes-agent"), help="Hermes agent checkout directory")
    customization_parser.add_argument("--hermes-config", default="", help="Hermes config.yaml path; defaults to <hermes-home>/config.yaml")
    customization_parser.add_argument("--include-network", action="store_true", help="Also probe external backends such as VoxCPM health")

    lifecycle_parser = subparsers.add_parser("hermes-skill-lifecycle-audit", help="Passively audit Hermes skill lifecycle metadata, staleness, archives, and negative-claim revalidation candidates")
    lifecycle_parser.add_argument("--hermes-home", default=str(Path.home() / ".hermes"), help="Hermes home directory")
    lifecycle_parser.add_argument("--hermes-config", default="", help="Hermes config.yaml path; defaults to <hermes-home>/config.yaml")
    lifecycle_parser.add_argument("--no-external-dirs", action="store_true", help="Only scan ~/.hermes/skills; skip skills.external_dirs")
    lifecycle_parser.add_argument("--telemetry-path", default="state/hermes-skill-usage.json", help="ZeusOS telemetry sidecar JSON path")
    lifecycle_parser.add_argument("--stale-after-days", type=int, default=30, help="Age threshold for stale review")
    lifecycle_parser.add_argument("--archive-after-days", type=int, default=90, help="Age threshold for archive candidates")
    lifecycle_parser.add_argument("--negative-claim-ttl-days", type=int, default=14, help="TTL before old negative/environment-dependent claims need revalidation")

    skill_search_index_parser = subparsers.add_parser("hermes-skill-search-index", help="Build the ZeusOS-owned Hermes skill retrieval FTS sidecar")
    skill_search_index_parser.add_argument("--db", default=str(DEFAULT_SKILL_SEARCH_DB), help="SQLite sidecar path")
    skill_search_index_parser.add_argument("--hermes-home", default=str(Path.home() / ".hermes"), help="Hermes home directory")
    skill_search_index_parser.add_argument("--hermes-config", default="", help="Hermes config.yaml path for skills.external_dirs")
    skill_search_index_parser.add_argument("--skill-root", action="append", default=None, help="Explicit skill root to scan; repeatable and overrides defaults")
    skill_search_index_parser.add_argument("--telemetry-path", default="state/hermes-skill-usage.json", help="ZeusOS telemetry sidecar JSON path; use empty string to disable")

    skill_search_parser = subparsers.add_parser("hermes-skill-search", help="Search the ZeusOS-owned Hermes skill retrieval sidecar")
    skill_search_parser.add_argument("--db", default=str(DEFAULT_SKILL_SEARCH_DB), help="SQLite sidecar path")
    skill_search_parser.add_argument("--query", required=True, help="Skill search query")
    skill_search_parser.add_argument("--top-k", type=int, default=5, help="Maximum result rows")
    skill_search_parser.add_argument("--include-archived", action="store_true", help="Include archived skills with penalties")
    skill_search_parser.add_argument("--search-log-path", default="", help="Optional ZeusOS-owned JSONL search log path")
    skill_search_parser.add_argument("--selected-skill", default="", help="Optional selected skill name to include in the search log")
    skill_search_parser.add_argument("--clicked-skill", default="", help="Optional clicked skill name to include in the search log")
    skill_search_parser.add_argument("--format", choices=("json", "table", "names-only"), default="json", help="Output format")

    skill_search_eval_parser = subparsers.add_parser("hermes-skill-search-eval", help="Evaluate Hermes skill search against a gold query fixture")
    skill_search_eval_parser.add_argument("--db", default=str(DEFAULT_SKILL_SEARCH_DB), help="SQLite sidecar path")
    skill_search_eval_parser.add_argument("--gold", required=True, help="Gold query JSON fixture path")
    skill_search_eval_parser.add_argument("--k", type=int, default=5, help="K for Recall@K and MRR@K")
    skill_search_eval_parser.add_argument("--include-archived", action="store_true", help="Include archived skills with penalties")

    skill_context_parser = subparsers.add_parser("hermes-skill-context", help="Generate budget-aware Hermes skill context snippets")
    skill_context_parser.add_argument("--db", default=str(DEFAULT_SKILL_SEARCH_DB), help="SQLite sidecar path")
    skill_context_parser.add_argument("--query", required=True, help="Skill search query")
    skill_context_parser.add_argument("--top-k", type=int, default=5, help="Maximum result rows to consider")
    skill_context_parser.add_argument("--budget", type=int, default=2000, help="Approximate token budget")
    skill_context_parser.add_argument("--format", choices=("json", "table", "names-only"), default="json", help="Output format")

    telemetry_parser = subparsers.add_parser("hermes-skill-telemetry", help="Record ZeusOS-owned Hermes skill lifecycle telemetry without modifying Hermes source")
    telemetry_subparsers = telemetry_parser.add_subparsers(dest="telemetry_command", required=True)
    telemetry_record_parser = telemetry_subparsers.add_parser("record", help="Record a viewed/used/successful_apply/patched event for a skill")
    telemetry_record_parser.add_argument("--skill", default="", help="Skill name or directory basename")
    telemetry_record_parser.add_argument("--skill-path", default="", help="Explicit skill directory or SKILL.md path")
    telemetry_record_parser.add_argument("--event", required=True, choices=("viewed", "used", "successful_apply", "patched"), help="Telemetry event kind")
    telemetry_record_parser.add_argument("--hermes-home", default=str(Path.home() / ".hermes"), help="Hermes home directory")
    telemetry_record_parser.add_argument("--hermes-config", default="", help="Hermes config.yaml path; defaults to <hermes-home>/config.yaml")
    telemetry_record_parser.add_argument("--telemetry-path", default="state/hermes-skill-usage.json", help="ZeusOS telemetry sidecar JSON path")
    telemetry_record_parser.add_argument("--no-external-dirs", action="store_true", help="Only scan ~/.hermes/skills; skip skills.external_dirs")
    telemetry_record_parser.add_argument("--pinned", action="store_true", help="Mark the skill as pinned in ZeusOS telemetry")
    telemetry_record_parser.add_argument("--unpinned", action="store_true", help="Mark the skill as not pinned in ZeusOS telemetry")

    samples_parser = subparsers.add_parser("styled-voice-samples", help="Manage the ZeusOS styled-voice sample library")
    samples_subparsers = samples_parser.add_subparsers(dest="sample_command", required=True)

    samples_init_parser = samples_subparsers.add_parser("init", help="Create the sample library and default profile directories")
    samples_init_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
    samples_init_parser.add_argument("--profile", action="append", default=None, help="Profile to create, e.g. default or jongwon/calm")

    samples_list_parser = samples_subparsers.add_parser("list", help="List stored voice profiles and sample files")
    samples_list_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")

    samples_path_parser = samples_subparsers.add_parser("path", help="Print the directory path for a profile")
    samples_path_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
    samples_path_parser.add_argument("--profile", default="default", help="Profile, e.g. default, jongwon, jongwon/calm")

    samples_add_parser = samples_subparsers.add_parser("add", help="Copy uploaded/local audio files into a person/style profile")
    samples_add_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
    samples_add_parser.add_argument("--profile", default="default", help="Profile, e.g. default, jongwon, jongwon/calm")
    samples_add_parser.add_argument("--audio", action="append", required=True, help="Audio file to copy into the profile; repeatable")
    samples_add_parser.add_argument("--move", action="store_true", help="Move instead of copy")

    samples_refs_parser = samples_subparsers.add_parser("refs", help="Print reference audio files for a profile")
    samples_refs_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
    samples_refs_parser.add_argument("--profile", default="default", help="Profile, e.g. default, jongwon, jongwon/calm")

    houroboros_parser = subparsers.add_parser("houroboros", aliases=["hooo"], help="Run the ZeusOS-native Houroboros workflow harness")
    houroboros_subparsers = houroboros_parser.add_subparsers(dest="houroboros_command", required=True)

    houroboros_start_parser = houroboros_subparsers.add_parser("start", help="Start an interview-backed Houroboros run")
    houroboros_start_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    houroboros_start_parser.add_argument("--goal", required=True, help="Workflow goal to crystallize")
    houroboros_start_parser.add_argument("--origin-platform", default="", help="Optional origin platform, e.g. discord")
    houroboros_start_parser.add_argument("--origin-channel-id", default="", help="Optional origin channel ID")
    houroboros_start_parser.add_argument("--origin-thread-id", default="", help="Optional origin thread ID")
    houroboros_start_parser.add_argument("--origin-message-id", default="", help="Optional origin Discord message ID")
    houroboros_start_parser.add_argument("--auto-open-thread", action="store_true", help="Request Discord thread creation through the safe ZeusOS handoff adapter")
    houroboros_start_parser.add_argument("--thread-name", default="", help="Optional Discord thread name for the handoff request")

    houroboros_mark_thread_parser = houroboros_subparsers.add_parser("mark-thread-created", help="Mark a pending Discord thread handoff as created")
    houroboros_mark_thread_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    houroboros_mark_thread_parser.add_argument("--run-id", required=True, help="Houroboros run ID")
    houroboros_mark_thread_parser.add_argument("--thread-id", required=True, help="Created Discord thread ID")
    houroboros_mark_thread_parser.add_argument("--thread-name", default="", help="Created Discord thread name")
    houroboros_mark_thread_parser.add_argument("--message-id", default="", help="Discord message ID associated with thread creation")
    houroboros_mark_thread_parser.add_argument("--jump-url", default="", help="Discord jump URL for the created thread")
    houroboros_mark_thread_parser.add_argument("--url", default="", help="Discord thread URL")

    houroboros_turn_parser = houroboros_subparsers.add_parser("turn", help="Append an interview turn")
    houroboros_turn_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    houroboros_turn_parser.add_argument("--run-id", required=True, help="Houroboros run ID")
    houroboros_turn_parser.add_argument("--message", required=True, help="Interview message to append")

    houroboros_interact_parser = houroboros_subparsers.add_parser("interact", help="Safely reduce a Discord button interaction into the ZeusOS state machine")
    houroboros_interact_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
    houroboros_interact_parser.add_argument("--run-id", required=True, help="Houroboros run ID")
    houroboros_interact_parser.add_argument(
        "--action",
        choices=("select_proposal", "other_opinion", "continue_interview", "propose_seed", "cancel"),
        default="",
        help="Logical HOOO interaction action; optional when --custom-id is provided",
    )
    houroboros_interact_parser.add_argument("--custom-id", default="", help="Discord component custom_id; when present it must match the run/action/revision")
    houroboros_interact_parser.add_argument("--card-revision", type=int, default=None, help="Card revision seen by the Discord interaction")
    houroboros_interact_parser.add_argument("--origin-channel-id", default="", help="Discord channel ID from the interaction callback")
    houroboros_interact_parser.add_argument("--origin-thread-id", default="", help="Discord thread ID from the interaction callback")
    houroboros_interact_parser.add_argument("--actor-id", default="", help="Discord actor/user ID from the interaction callback")

    for command_name in ("seed", "run", "evaluate", "evolve", "status", "export"):
        command_parser = houroboros_subparsers.add_parser(command_name, help=f"Houroboros {command_name}")
        command_parser.add_argument("--config", required=True, help="Path to pipeline.yaml")
        command_parser.add_argument("--run-id", required=True, help="Houroboros run ID")
        if command_name == "run":
            command_parser.add_argument("--executor", default="", help="Optional execution backend, e.g. claude-code")

    zeus_parser = subparsers.add_parser("zeus", help="Zeus OS control plane")
    zeus_subparsers = zeus_parser.add_subparsers(dest="zeus_command", required=True)
    populate_zeus_subparsers(zeus_subparsers)

    return parser


def main(argv: Sequence[str] | None = None, *, prog: str = "zeus-os") -> int:
    parser = build_parser(prog=prog)
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

    if args.command == "wiki-search-index":
        config = load_pipeline_config(args.config)
        result = rebuild_operational_search_index(config.database_path)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.command == "wiki-search":
        config = load_pipeline_config(args.config)
        result = search_operational_index(config.database_path, query=args.query, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.command == "wiki-semantic-lint":
        if not args.config and not args.wiki_root:
            parser.error("wiki-semantic-lint requires --config or --wiki-root")
        if args.wiki_root:
            wiki_root = Path(args.wiki_root).expanduser()
        else:
            config = load_pipeline_config(args.config)
            wiki_root = config.wiki_root
        result = lint_wiki_semantics(wiki_root)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

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

    if args.command == "sync-watch-sources":
        config = load_pipeline_config(args.config)
        result = sync_watch_sources(config)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "collect-watch-signals":
        config = load_pipeline_config(args.config)
        result = collect_watch_signals(config)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "build-watch-stories":
        config = load_pipeline_config(args.config)
        result = build_watch_stories(config)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "judge-watch-issues":
        config = load_pipeline_config(args.config)
        result = judge_watch_issues(config)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "generate-watch-report":
        config = load_pipeline_config(args.config)
        result = generate_watch_report(config, report_kind=args.report_kind)
        print(json.dumps({**result, "artifact_path": str(result["artifact_path"])}, ensure_ascii=False))
        return 0

    if args.command == "generate-external-hot-issue-alert":
        result = generate_external_hot_issue_alert(report_path=Path(args.report_path), state_path=Path(args.state_path))
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "generate-personal-radar-source-audit":
        result = generate_personal_radar_source_audit(registry_dir=Path(args.registry_dir), output_dir=Path(args.output_dir))
        print(json.dumps({**result, "artifact_path": str(result["artifact_path"]), "json_path": str(result["json_path"])}, ensure_ascii=False))
        return 0

    if args.command == "verify-personal-radar-coverage":
        result = generate_personal_radar_coverage_verification(registry_dir=Path(args.registry_dir), output_dir=Path(args.output_dir), live=not args.no_live)
        print(json.dumps({**result, "json_path": str(result["json_path"])}, ensure_ascii=False))
        return 0

    if args.command == "generate-news-center":
        config = load_pipeline_config(args.config) if args.config else None
        taxonomy_path = Path(args.taxonomy)
        if not taxonomy_path.is_absolute() and config is not None:
            taxonomy_path = config.workspace_root / taxonomy_path
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute() and config is not None:
            output_dir = config.workspace_root / output_dir
        wiki_root = Path(args.wiki_root).expanduser() if args.wiki_root else (config.wiki_root if config is not None else Path.home() / "wiki")
        result = collect_news_center(
            taxonomy_path=taxonomy_path,
            output_dir=output_dir,
            wiki_root=wiki_root,
            per_source_limit=args.per_source_limit,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "append-news-center-to-daily-report":
        news_markdown = Path(args.news_markdown).read_text(encoding="utf-8")
        append_news_center_to_daily_report(Path(args.daily_report), news_markdown)
        print(json.dumps({"daily_report": args.daily_report, "updated": True}, ensure_ascii=False))
        return 0

    if args.command == "generate-unified-daily-report":
        config = load_pipeline_config(args.config)
        result = generate_unified_daily_report(
            report_date=args.date,
            wiki_root=config.wiki_root,
            workspace_root=config.workspace_root,
            hot_issue_path=Path(args.hot_issue) if args.hot_issue else None,
            news_json_path=Path(args.news_json) if args.news_json else None,
            opportunity_json_path=Path(args.opportunity_json) if args.opportunity_json else None,
            delivery_gate=args.delivery_gate,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "generate-podcast-script":
        result = generate_podcast_script(Path(args.daily_report), output_path=Path(args.output_path), max_items=args.max_items)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "run-watch-cycle":
        config = load_pipeline_config(args.config)
        result = run_watch_cycle(config)
        print(json.dumps({
            "source_count": result["sync"]["source_count"],
            "signal_count": result["collect"]["signal_count"],
            "issue_count": result["build"]["issue_count"],
            "judged_count": result["judge"]["judged_count"],
            "report_path": str(result["report"]["artifact_path"]),
        }, ensure_ascii=False))
        return 0

    if args.command == "install-systemd":
        config = load_pipeline_config(args.config)
        result = install_systemd_user_units(config, poll_minutes=args.poll_minutes, enable=not args.no_enable)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "install-standby-systemd":
        config = load_pipeline_config(args.config)
        result = install_hermes_standby_units(
            config,
            health_minutes=args.health_minutes,
            discord_channel=args.discord_channel,
            stale_minutes=args.stale_minutes,
            enable=not args.no_enable,
            install_gateway=args.install_gateway,
            workspace_only=args.workspace_only,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "hermes-health-check":
        config = load_pipeline_config(args.config)
        result = check_hermes_zeusos_health(
            config,
            stale_minutes=args.stale_minutes,
            restart=args.restart,
            discord_alert=args.discord_alert,
            discord_channel=args.discord_channel,
            readiness_timeout_seconds=args.readiness_timeout_seconds,
            discord_api_check=not args.skip_discord_api_check,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "hermes-customization-check":
        result = check_hermes_customizations(
            hermes_home=args.hermes_home,
            hermes_agent_dir=args.hermes_agent_dir,
            hermes_config_path=args.hermes_config or None,
            include_network=args.include_network,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.command == "hermes-skill-lifecycle-audit":
        result = audit_hermes_skill_lifecycle(
            hermes_home=args.hermes_home,
            hermes_config_path=args.hermes_config or None,
            include_external_dirs=not args.no_external_dirs,
            stale_after_days=args.stale_after_days,
            archive_after_days=args.archive_after_days,
            negative_claim_ttl_days=args.negative_claim_ttl_days,
            telemetry_path=args.telemetry_path,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.command == "hermes-skill-search-index":
        result = build_skill_search_index(
            args.db,
            hermes_home=args.hermes_home,
            hermes_config_path=args.hermes_config or None,
            skill_roots=args.skill_root,
            telemetry_path=args.telemetry_path or None,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.command == "hermes-skill-search":
        result = search_skills(
            args.db,
            args.query,
            top_k=args.top_k,
            include_archived=args.include_archived,
            search_log_path=args.search_log_path or None,
            selected_skill=args.selected_skill or None,
            clicked_skill=args.clicked_skill or None,
        )
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False))
        elif args.format == "names-only":
            print("\n".join(str(row["name"]) for row in result.get("rows", [])))
        else:
            print("rank\tscore\tname\tpath")
            for row in result.get("rows", []):
                print(f"{row['rank']}\t{row['score']}\t{row['name']}\t{row['path']}")
        return 0 if result.get("ok") else 1

    if args.command == "hermes-skill-search-eval":
        result = evaluate_skill_search(args.db, args.gold, k=args.k, include_archived=args.include_archived)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.command == "hermes-skill-context":
        result = generate_skill_context(args.db, args.query, budget_tokens=args.budget, top_k=args.top_k)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False))
        elif args.format == "names-only":
            print("\n".join(str(row["name"]) for row in result.get("snippets", [])))
        else:
            print(result.get("context", ""))
        return 0 if result.get("ok") else 1

    if args.command == "hermes-skill-telemetry":
        if args.pinned and args.unpinned:
            parser.error("--pinned and --unpinned are mutually exclusive")
        pinned = True if args.pinned else False if args.unpinned else None
        result = record_skill_telemetry(
            skill=args.skill or None,
            skill_path=args.skill_path or None,
            event=args.event,
            hermes_home=args.hermes_home,
            hermes_config_path=args.hermes_config or None,
            telemetry_path=args.telemetry_path,
            include_external_dirs=not args.no_external_dirs,
            pinned=pinned,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.command == "styled-voice-samples":
        library_dir = args.library_dir or None
        if args.sample_command == "init":
            result = init_styled_voice_library(library_dir, profiles=args.profile or ["default"])
        elif args.sample_command == "list":
            result = {"profiles": list_styled_voice_profiles(library_dir)}
        elif args.sample_command == "path":
            result = {"profile": args.profile, "path": str(styled_voice_profile_dir(library_dir, args.profile).resolve())}
        elif args.sample_command == "add":
            result = add_styled_voice_samples(args.audio, library_dir, args.profile, copy=not args.move)
        elif args.sample_command == "refs":
            result = {"profile": args.profile, "references": [str(path) for path in collect_profile_audio(library_dir, args.profile)]}
        else:  # pragma: no cover
            parser.error(f"Unknown styled-voice-samples command: {args.sample_command}")
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command in {"houroboros", "hooo"}:
        workflow = HouroborosWorkflow.from_config_path(args.config)
        try:
            if args.houroboros_command == "start":
                result = workflow.start(
                    goal=args.goal,
                    origin_platform=args.origin_platform,
                    origin_channel_id=args.origin_channel_id,
                    origin_thread_id=args.origin_thread_id,
                    origin_message_id=args.origin_message_id,
                    auto_open_thread=args.auto_open_thread,
                    thread_name=args.thread_name,
                )
            elif args.houroboros_command == "turn":
                result = workflow.turn(args.run_id, args.message)
            elif args.houroboros_command == "interact":
                result = workflow.handle_interaction(
                    args.run_id,
                    args.action,
                    card_revision=args.card_revision,
                    custom_id=args.custom_id,
                    origin_channel_id=args.origin_channel_id,
                    origin_thread_id=args.origin_thread_id,
                    actor_id=args.actor_id,
                )
            elif args.houroboros_command == "seed":
                result = workflow.seed(args.run_id)
            elif args.houroboros_command == "run":
                result = workflow.run(args.run_id, executor=args.executor)
            elif args.houroboros_command == "evaluate":
                result = workflow.evaluate(args.run_id)
            elif args.houroboros_command == "evolve":
                result = workflow.evolve(args.run_id)
            elif args.houroboros_command == "mark-thread-created":
                result = workflow.mark_thread_created(
                    args.run_id,
                    thread_id=args.thread_id,
                    thread_name=args.thread_name,
                    message_id=args.message_id,
                    jump_url=args.jump_url,
                    url=args.url,
                )
            elif args.houroboros_command == "status":
                result = workflow.status(args.run_id)
            elif args.houroboros_command == "export":
                result = workflow.export(args.run_id)
            else:  # pragma: no cover
                parser.error(f"Unknown houroboros command: {args.houroboros_command}")
        except (FileNotFoundError, KeyError, ValueError, sqlite3.IntegrityError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "zeus":
        return handle_zeus(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
