# Wiki path dependency map
src/jinwang_jarvis/intelligence.py:78:INTELLIGENCE_NOTE_DIR = "queries/jinwang-jarvis-intelligence"
src/jinwang_jarvis/intelligence.py:94:MONTHLY_TIMELINE_NOTE = "queries/jinwang-jarvis-monthly-timeline-36m.md"
src/jinwang_jarvis/knowledge.py:13:WATCHLIST_NOTE_RELATIVE_PATH = "queries/jinwang-jarvis-importance-shift-watchlist.md"
src/jinwang_jarvis/knowledge.py:14:WATCHLIST_INDEX_LINE = "- [[jinwang-jarvis-importance-shift-watchlist]] — Rolling watchlist of suppressed-but-promotable mail threads and the current importance-shift patterns in Jinwang Jarvis."
src/jinwang_jarvis/knowledge.py:15:SENT_MAIL_MEMORY_INDEX_LINE = "- [[queries/jinwang-jarvis-memory/sent-mail-memory|Jinwang Jarvis Sent Mail Memory]] — 보낸편지함 메일을 신규 수신 추천에서는 제외하되, 실제 발신·회신·공유·결정 맥락을 계층적으로 저장하는 generated memory shard."
src/jinwang_jarvis/knowledge.py:16:MEMORY_NOTE_DIR = "queries/jinwang-jarvis-memory"
src/jinwang_jarvis/knowledge.py:309:        "- [[queries/jinwang-jarvis-mvp-completion-april-2026]]",
src/jinwang_jarvis/knowledge.py:310:        "- [[queries/jinwang-jarvis-memory/index]]",
src/jinwang_jarvis/knowledge.py:518:        "- [[queries/jinwang-jarvis-memory/recent-important]]",
src/jinwang_jarvis/knowledge.py:519:        "- [[queries/jinwang-jarvis-memory/continuing-important]]",
src/jinwang_jarvis/knowledge.py:520:        "- [[queries/jinwang-jarvis-memory/newly-important]]",
src/jinwang_jarvis/knowledge.py:521:        "- [[queries/jinwang-jarvis-memory/schedule-recommendations]]",
src/jinwang_jarvis/knowledge.py:522:        "- [[queries/jinwang-jarvis-memory/sent-mail-memory]]",
src/jinwang_jarvis/knowledge.py:523:        "- [[queries/jinwang-jarvis-importance-shift-watchlist]]",
src/jinwang_jarvis/wiki_semantic_lint.py:6:GENERATED_PREFIXES = ("reports/", "queries/jinwang-jarvis-", "queries/external-hot-issues/")
src/jinwang_jarvis/wiki_semantic_lint.py:61:    return rel_path.startswith("queries/") and not rel_path.startswith(("queries/jinwang-jarvis-", "queries/external-hot-issues/"))
tests/test_knowledge.py:191:    assert "jinwang-jarvis-importance-shift-watchlist" in index_text
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
