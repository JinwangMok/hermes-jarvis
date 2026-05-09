# Hardcoded path inventory

## src/ and tests absolute repo path references
tests/test_daily_hot_issues_pdf_renderer.py:122:- source: /home/jinwang/workspace/jinwang-jarvis/data/internal.json
tests/test_config.py:12:    assert config.workspace_root == Path("/home/jinwang/workspace/jinwang-jarvis")
tests/test_config.py:13:    assert config.wiki_root == Path("/home/jinwang/workspace/jinwang-jarvis/wiki")
tests/test_config.py:14:    assert config.database_path == Path("/home/jinwang/workspace/jinwang-jarvis/state/personal_intel.db")
tests/test_config.py:15:    assert config.sender_map_path == Path("/home/jinwang/workspace/jinwang-jarvis/config/sender-map.example.md")
tests/test_config.py:16:    assert config.mail_snapshot_dir == Path("/home/jinwang/workspace/jinwang-jarvis/data/snapshots/mail")
tests/test_config.py:17:    assert config.calendar_snapshot_dir == Path("/home/jinwang/workspace/jinwang-jarvis/data/snapshots/calendar")
tests/test_config.py:24:    assert config.watch.source_config_dir == Path("/home/jinwang/workspace/jinwang-jarvis/config/watch-sources")

## styled voice / workspace path references
src/jinwang_jarvis/wiki_contract.py:16:    jinwang-jarvis treats the wiki as a dynamic knowledge substrate for Hermes:
src/jinwang_jarvis/wiki_contract.py:170:    generator: str = "jinwang-jarvis",
src/jinwang_jarvis/wiki_contract.py:227:        generator="jinwang-jarvis",
src/jinwang_jarvis/wiki_contract.py:264:    return "jinwang-jarvis configured SQLite database/artifacts"
src/jinwang_jarvis/cli.py:30:from .styled_voice_samples import add_samples as add_styled_voice_samples
src/jinwang_jarvis/cli.py:31:from .styled_voice_samples import collect_profile_audio, init_library as init_styled_voice_library, list_profiles as list_styled_voice_profiles, profile_dir as styled_voice_profile_dir
src/jinwang_jarvis/cli.py:40:    parser = argparse.ArgumentParser(prog="jinwang-jarvis")
src/jinwang_jarvis/cli.py:193:    customization_parser = subparsers.add_parser("hermes-customization-check", help="Passively inspect the Hermes agent + jinwang-jarvis customization contract")
src/jinwang_jarvis/cli.py:251:    samples_parser = subparsers.add_parser("styled-voice-samples", help="Manage the Jarvis styled-voice sample library")
src/jinwang_jarvis/cli.py:255:    samples_init_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
src/jinwang_jarvis/cli.py:259:    samples_list_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
src/jinwang_jarvis/cli.py:262:    samples_path_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
src/jinwang_jarvis/cli.py:266:    samples_add_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
src/jinwang_jarvis/cli.py:272:    samples_refs_parser.add_argument("--library-dir", default="", help="Sample library root; defaults to data/styled-voice-samples")
src/jinwang_jarvis/cli.py:832:    if args.command == "styled-voice-samples":
src/jinwang_jarvis/cli.py:841:            result = add_styled_voice_samples(args.audio, library_dir, args.profile, copy=not args.move)
src/jinwang_jarvis/cli.py:845:            parser.error(f"Unknown styled-voice-samples command: {args.sample_command}")
src/jinwang_jarvis/hermes_continuity.py:198:        "contract": "Hermes agent + jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:78:INTELLIGENCE_NOTE_DIR = "queries/jinwang-jarvis-intelligence"
src/jinwang_jarvis/intelligence.py:94:MONTHLY_TIMELINE_NOTE = "queries/jinwang-jarvis-monthly-timeline-36m.md"
src/jinwang_jarvis/intelligence.py:1021:        'generator: jinwang-jarvis',
src/jinwang_jarvis/intelligence.py:1169:        'generator: jinwang-jarvis',
src/jinwang_jarvis/intelligence.py:1476:        'generator: jinwang-jarvis',
src/jinwang_jarvis/intelligence.py:1558:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:1625:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:1664:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:1730:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:1775:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:1820:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:1861:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:1950:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:2129:        "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:2205:            "generator: jinwang-jarvis",
src/jinwang_jarvis/intelligence.py:2250:        "generator: jinwang-jarvis",
src/jinwang_jarvis/knowledge.py:13:WATCHLIST_NOTE_RELATIVE_PATH = "queries/jinwang-jarvis-importance-shift-watchlist.md"
src/jinwang_jarvis/knowledge.py:14:WATCHLIST_INDEX_LINE = "- [[jinwang-jarvis-importance-shift-watchlist]] — Rolling watchlist of suppressed-but-promotable mail threads and the current importance-shift patterns in Jinwang Jarvis."
src/jinwang_jarvis/knowledge.py:15:SENT_MAIL_MEMORY_INDEX_LINE = "- [[queries/jinwang-jarvis-memory/sent-mail-memory|Jinwang Jarvis Sent Mail Memory]] — 보낸편지함 메일을 신규 수신 추천에서는 제외하되, 실제 발신·회신·공유·결정 맥락을 계층적으로 저장하는 generated memory shard."
src/jinwang_jarvis/knowledge.py:16:MEMORY_NOTE_DIR = "queries/jinwang-jarvis-memory"
src/jinwang_jarvis/knowledge.py:258:        "generator: jinwang-jarvis",
src/jinwang_jarvis/knowledge.py:307:        "- [[entities/jinwang-jarvis]]",
src/jinwang_jarvis/knowledge.py:309:        "- [[queries/jinwang-jarvis-mvp-completion-april-2026]]",
src/jinwang_jarvis/knowledge.py:310:        "- [[queries/jinwang-jarvis-memory/index]]",
src/jinwang_jarvis/knowledge.py:388:        "generator: jinwang-jarvis",
src/jinwang_jarvis/knowledge.py:445:        "generator: jinwang-jarvis",
src/jinwang_jarvis/knowledge.py:508:        "generator: jinwang-jarvis",
src/jinwang_jarvis/knowledge.py:518:        "- [[queries/jinwang-jarvis-memory/recent-important]]",
src/jinwang_jarvis/knowledge.py:519:        "- [[queries/jinwang-jarvis-memory/continuing-important]]",
src/jinwang_jarvis/knowledge.py:520:        "- [[queries/jinwang-jarvis-memory/newly-important]]",
src/jinwang_jarvis/knowledge.py:521:        "- [[queries/jinwang-jarvis-memory/schedule-recommendations]]",
src/jinwang_jarvis/knowledge.py:522:        "- [[queries/jinwang-jarvis-memory/sent-mail-memory]]",
src/jinwang_jarvis/knowledge.py:523:        "- [[queries/jinwang-jarvis-importance-shift-watchlist]]",
src/jinwang_jarvis/styled_voice_samples.py:13:    "~/workspace/jinwang-jarvis/data/styled-voice-samples",
src/jinwang_jarvis/unified_daily_report.py:323:    req = urllib.request.Request(url, headers={"User-Agent": "jinwang-jarvis-unified-daily-report/0.1"})
src/jinwang_jarvis/unified_daily_report.py:612:        "generator: jinwang-jarvis-unified-daily-report",
src/jinwang_jarvis/zeus_os/cli.py:15:    parser = argparse.ArgumentParser(prog="jinwang-jarvis zeus")
src/jinwang_jarvis/runtime.py:29:CYCLE_SERVICE_NAME = "jinwang-jarvis-cycle.service"
src/jinwang_jarvis/runtime.py:30:CYCLE_TIMER_NAME = "jinwang-jarvis-cycle.timer"
src/jinwang_jarvis/runtime.py:31:WEEKLY_SERVICE_NAME = "jinwang-jarvis-weekly-review.service"
src/jinwang_jarvis/runtime.py:32:WEEKLY_TIMER_NAME = "jinwang-jarvis-weekly-review.timer"
src/jinwang_jarvis/runtime.py:34:HERMES_HEALTH_SERVICE_NAME = "jinwang-jarvis-hermes-health.service"
src/jinwang_jarvis/runtime.py:35:HERMES_HEALTH_TIMER_NAME = "jinwang-jarvis-hermes-health.timer"
src/jinwang_jarvis/runtime.py:146:Unit=jinwang-jarvis-weekly-review.service
src/jinwang_jarvis/runtime.py:395:        headers={"Authorization": f"Bot {token}", "User-Agent": "jinwang-jarvis-health-check/0.1"},
src/jinwang_jarvis/runtime.py:477:            "User-Agent": "jinwang-jarvis-health-check/0.1",
src/jinwang_jarvis/hermes_skill_lifecycle.py:340:        "contract": "Hermes agent + jinwang-jarvis",
src/jinwang_jarvis/personal_radar.py:212:        "generator: jinwang-jarvis-personal-radar",
src/jinwang_jarvis/wiki_semantic_lint.py:6:GENERATED_PREFIXES = ("reports/", "queries/jinwang-jarvis-", "queries/external-hot-issues/")
src/jinwang_jarvis/wiki_semantic_lint.py:61:    return rel_path.startswith("queries/") and not rel_path.startswith(("queries/jinwang-jarvis-", "queries/external-hot-issues/"))
src/jinwang_jarvis/news_crawlers/collector.py:65:    req = urllib.request.Request(url, headers={"User-Agent": "jinwang-jarvis-news-center/0.2"})
tests/test_briefing.py:39:  project_name: jinwang-jarvis
tests/test_wiki_search.py:31:  project_name: jinwang-jarvis
tests/test_cli.py:36:  project_name: jinwang-jarvis
tests/test_cli.py:205:    assert (tmp_path / "systemd" / "jinwang-jarvis-cycle.timer").exists()
tests/test_cli.py:222:    assert (tmp_path / "systemd" / "jinwang-jarvis-hermes-health.timer").exists()
tests/test_daily_hot_issues_pdf_renderer.py:122:- source: /home/jinwang/workspace/jinwang-jarvis/data/internal.json
tests/test_feedback_review_backfill.py:41:  project_name: jinwang-jarvis
tests/fixtures/hermes_skill_gold_queries.json:5:      "expected_skill_names": ["jinwang-jarvis", "hermes-jinwang-customization"]
tests/fixtures/hermes_skill_gold_queries.json:21:      "expected_skill_names": ["jinwang-jarvis", "hermes-agent"]
tests/test_hermes_skill_search.py:217:    _write_skill(root / "jinwang-jarvis", description="Jarvis source untouched sidecar", body="Source untouched Jarvis skill retrieval context budget.")
tests/test_bootstrap.py:31:  project_name: jinwang-jarvis
tests/test_classification_pipeline.py:50:  project_name: jinwang-jarvis
tests/test_minerva.py:49:  project_name: jinwang-jarvis
tests/test_watch.py:137:  project_name: jinwang-jarvis
tests/test_unified_daily_report.py:585:  project_name: jinwang-jarvis
tests/test_unified_daily_report.py:635:  project_name: jinwang-jarvis
tests/test_hermes_skill_lifecycle.py:98:    external_skills = tmp_path / "jinwang-jarvis" / "skills"
tests/test_knowledge.py:44:  project_name: jinwang-jarvis
tests/test_knowledge.py:182:    assert "generator: jinwang-jarvis" in wiki_text
tests/test_knowledge.py:191:    assert "jinwang-jarvis-importance-shift-watchlist" in index_text
tests/test_mail_collection.py:78:  project_name: jinwang-jarvis
tests/test_hermes_continuity.py:9:    jarvis_skills = tmp_path / "jinwang-jarvis" / "skills"
tests/test_hermes_continuity.py:33:    assert result["contract"] == "Hermes agent + jinwang-jarvis"
tests/test_styled_voice_samples.py:5:from jinwang_jarvis.styled_voice_samples import add_samples, collect_profile_audio, list_profiles, parse_profile, profile_dir, sanitize_label
tests/test_calendar_collection.py:81:  project_name: jinwang-jarvis
tests/test_proposals.py:46:  project_name: jinwang-jarvis
tests/test_intelligence.py:69:  project_name: jinwang-jarvis
tests/test_intelligence.py:452:    assert "generator: jinwang-jarvis" in wiki_text
tests/test_intelligence.py:553:    flow_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-smartx-flow.md"
tests/test_intelligence.py:719:    direct_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-direct-actions.md"
tests/test_intelligence.py:720:    weekly_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/smartx-weekly-briefing.md"
tests/test_intelligence.py:721:    phase_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-phase-map.md"
tests/test_intelligence.py:722:    context_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/jongwon-context-cases.md"
tests/test_intelligence.py:723:    chain_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/interaction-chain-status.md"
tests/test_intelligence.py:724:    advisor_action_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/advisor-action-status.md"
tests/test_intelligence.py:725:    education_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/education-teaching-memory.md"
tests/test_intelligence.py:726:    project_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/project-work-items.md"
tests/test_intelligence.py:727:    recent_action_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/recent-action-alerts.md"
tests/test_intelligence.py:728:    next_day_todo_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/next-day-mail-todos.md"
tests/test_intelligence.py:729:    important_mail_note = config.wiki_root / "queries/jinwang-jarvis-intelligence/priority/important-mail-recommendations.md"
tests/test_runtime.py:35:  project_name: jinwang-jarvis
tests/test_runtime.py:107:  project_name: jinwang-jarvis
tests/test_runtime.py:115:    assert "Persistent=true" in units["jinwang-jarvis-cycle.timer"]
tests/test_runtime.py:116:    assert "OnUnitActiveSec=15min" in units["jinwang-jarvis-cycle.timer"]
tests/test_runtime.py:117:    assert "run-cycle --config pipeline.yaml" in units["jinwang-jarvis-cycle.service"]
tests/test_runtime.py:118:    assert "Environment=PATH=" in units["jinwang-jarvis-cycle.service"]
tests/test_runtime.py:119:    assert "OnCalendar=Sun *-*-* 20:00:00" in units["jinwang-jarvis-weekly-review.timer"]
tests/test_runtime.py:150:  project_name: jinwang-jarvis
tests/test_runtime.py:164:    assert "EnvironmentFile=-" in units["jinwang-jarvis-hermes-health.service"]
tests/test_runtime.py:165:    assert ".hermes/.env" in units["jinwang-jarvis-hermes-health.service"]
tests/test_runtime.py:166:    assert "JARVIS_HEALTH_DISCORD_CHANNEL=1496014213276241922" in units["jinwang-jarvis-hermes-health.service"]
tests/test_runtime.py:167:    assert "hermes-health-check" in units["jinwang-jarvis-hermes-health.service"]
tests/test_runtime.py:168:    assert "--discord-alert --restart" in units["jinwang-jarvis-hermes-health.service"]
tests/test_runtime.py:169:    assert "--readiness-timeout-seconds 45" in units["jinwang-jarvis-hermes-health.service"]
tests/test_runtime.py:170:    assert "OnUnitActiveSec=5min" in units["jinwang-jarvis-hermes-health.timer"]
tests/test_runtime.py:171:    assert "Persistent=true" in units["jinwang-jarvis-hermes-health.timer"]
tests/test_config.py:11:    assert config.project_name == "jinwang-jarvis"
tests/test_config.py:12:    assert config.workspace_root == Path("/home/jinwang/workspace/jinwang-jarvis")
tests/test_config.py:13:    assert config.wiki_root == Path("/home/jinwang/workspace/jinwang-jarvis/wiki")
tests/test_config.py:14:    assert config.database_path == Path("/home/jinwang/workspace/jinwang-jarvis/state/personal_intel.db")
tests/test_config.py:15:    assert config.sender_map_path == Path("/home/jinwang/workspace/jinwang-jarvis/config/sender-map.example.md")
tests/test_config.py:16:    assert config.mail_snapshot_dir == Path("/home/jinwang/workspace/jinwang-jarvis/data/snapshots/mail")
tests/test_config.py:17:    assert config.calendar_snapshot_dir == Path("/home/jinwang/workspace/jinwang-jarvis/data/snapshots/calendar")
tests/test_config.py:24:    assert config.watch.source_config_dir == Path("/home/jinwang/workspace/jinwang-jarvis/config/watch-sources")
tests/test_wiki_semantic_lint.py:8:    generated = wiki / "queries" / "jinwang-jarvis-report.md"
config/pipeline.yaml:29:  project_name: jinwang-jarvis
config/pipeline.local.yaml:1:workspace_root: /home/jinwang/workspace/jinwang-jarvis
config/pipeline.local.yaml:33:  project_name: jinwang-jarvis
config/sender_rules.yaml:1:# Optional sender overrides for jinwang-jarvis
config/subject_rules.yaml:1:# Optional subject suppression / promotion patterns for jinwang-jarvis
config/workstream_rules.yaml:1:# Optional workstream mapping rules for jinwang-jarvis
systemd/jinwang-jarvis-hermes-health.service:8:WorkingDirectory=/home/jinwang/workspace/jinwang-jarvis
systemd/jinwang-jarvis-hermes-health.service:13:ExecStart=/bin/bash -lc 'cd /home/jinwang/workspace/jinwang-jarvis && PYTHONPATH=src python3 -m jinwang_jarvis.cli hermes-health-check --config config/pipeline.local.yaml --discord-alert --restart --stale-minutes 15 --readiness-timeout-seconds 45'
systemd/jinwang-jarvis-weekly-review.service:8:WorkingDirectory=/home/jinwang/workspace/jinwang-jarvis
systemd/jinwang-jarvis-weekly-review.service:10:ExecStart=/bin/bash -lc 'cd /home/jinwang/workspace/jinwang-jarvis && PYTHONPATH=src python3 -m jinwang_jarvis.cli weekly-review --config config/pipeline.local.yaml'
systemd/jinwang-jarvis-cycle.timer:8:Unit=jinwang-jarvis-cycle.service
systemd/jinwang-jarvis-hermes-health.timer:8:Unit=jinwang-jarvis-hermes-health.service
systemd/jinwang-jarvis-weekly-review.timer:7:Unit=jinwang-jarvis-weekly-review.service
systemd/jinwang-jarvis-cycle.service:8:WorkingDirectory=/home/jinwang/workspace/jinwang-jarvis
systemd/jinwang-jarvis-cycle.service:10:ExecStart=/bin/bash -lc 'cd /home/jinwang/workspace/jinwang-jarvis && PYTHONPATH=src python3 -m jinwang_jarvis.cli run-cycle --config config/pipeline.local.yaml'
systemd/hermes-gateway.service:14:ExecStartPre=-/bin/bash /home/jinwang/workspace/jinwang-jarvis/scripts/arm-opencode-gateway-recovery.sh systemd-ExecStartPre-hermes-gateway
scripts/install.sh:69:  systemctl --user disable --now jinwang-jarvis-cycle.timer jinwang-jarvis-weekly-review.timer >/dev/null 2>&1 || true
scripts/install.sh:70:  systemctl --user disable --now jinwang-jarvis-cycle.service jinwang-jarvis-weekly-review.service >/dev/null 2>&1 || true
scripts/gate_daily_hot_issues_delivery.py:73:    (re.compile(r"/home/jinwang|/workspace|jinwang-jarvis/data", re.I), "local path leaked"),
