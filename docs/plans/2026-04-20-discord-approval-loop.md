# Discord Approval Loop + Incremental Backfill Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a natural-language Jarvis briefing/approval loop that can ask in Discord whether proposed events should be added to Calendar, and extend backfill handling to support incremental 3-month growth (9m, 12m, ... 36m) without one-shot bulk expansion.

**Architecture:** Keep operational truth in SQLite/artifacts. Add a briefing module that reads proposal/mail state and emits Discord-ready natural-language summaries plus machine-readable pending approvals. Extend the feedback path so an explicit allow decision can optionally create a Google Calendar event via the Hermes-managed Google Workspace wrapper. Extend backfill window parsing so arbitrary `Nm` windows work and add a helper to determine the next 3-month step.

**Tech Stack:** Python 3, sqlite3, existing Jarvis CLI, Google Workspace wrapper script, pytest.

---

### Task 1: Inspect current state and add focused tests for incremental month windows
**Objective:** Lock down the desired 9m/12m/.../36m backfill behavior before implementation.

**Files:**
- Modify: `tests/test_feedback_review_backfill.py`
- Modify: `tests/test_cli.py`

**Step 1: Write failing tests**
- Add a test that `run_progressive_backfill(..., windows=("9m",))` succeeds and writes a `backfill-9m-*.json` artifact.
- Add a test for a helper/CLI surface that computes the next staged month window from checkpoints/current state.

**Step 2: Run targeted tests to verify failure**
Run: `pytest -q tests/test_feedback_review_backfill.py tests/test_cli.py`
Expected: FAIL because dynamic month parsing / helper command does not exist yet.

**Step 3: Implement minimal code**
- Add reusable month-window parsing in `src/jinwang_jarvis/backfill.py`.
- Add CLI surface for incremental next-step execution.

**Step 4: Run tests to verify pass**
Run: `pytest -q tests/test_feedback_review_backfill.py tests/test_cli.py`
Expected: PASS.

### Task 2: Add natural-language briefing generation tests
**Objective:** Define the output contract for recent/continuing/newly-important work and schedule recommendations.

**Files:**
- Create: `tests/test_briefing.py`

**Step 1: Write failing tests**
- Seed messages, proposals, and prior history.
- Assert the generated briefing artifact contains sections for:
  - 최근 중요한 일
  - 계속 중요한 일
  - 새로 중요해진 일
  - 추천 일정
  - approval prompt wording like `캘린더에 등록할까요?`
- Assert the artifact contains the configured Discord target channel string.

**Step 2: Run the new test**
Run: `pytest -q tests/test_briefing.py`
Expected: FAIL because the module/CLI does not exist.

**Step 3: Implement minimal code**
- Add a new briefing module that builds natural-language summary text + pending approval metadata.
- Persist an artifact under `data/briefings/`.

**Step 4: Run the test to verify pass**
Run: `pytest -q tests/test_briefing.py`
Expected: PASS.

### Task 3: Add approval-to-calendar-create tests
**Objective:** Ensure explicit allow decisions can create Calendar events through the existing OAuth wrapper, but still support dry approval when desired.

**Files:**
- Modify: `tests/test_feedback_review_backfill.py`
- Modify: `tests/test_cli.py`
- Modify: `src/jinwang_jarvis/feedback.py`
- Modify: `src/jinwang_jarvis/cli.py`

**Step 1: Write failing tests**
- Add a test that `record_proposal_feedback(..., decision="allow", create_calendar_event=True, runner=fake_runner)` calls the Google wrapper and writes the returned event metadata into the feedback artifact.
- Add a CLI test for `record-feedback --decision allow --create-calendar`.

**Step 2: Run targeted tests**
Run: `pytest -q tests/test_feedback_review_backfill.py tests/test_cli.py`
Expected: FAIL because `record_proposal_feedback` cannot create calendar events yet.

**Step 3: Implement minimal code**
- Add optional `create_calendar_event` support to `record_proposal_feedback`.
- Use the Hermes Google Workspace wrapper script, not raw API code.
- Keep reject/allow-without-calendar behavior unchanged.

**Step 4: Run tests to verify pass**
Run: `pytest -q tests/test_feedback_review_backfill.py tests/test_cli.py`
Expected: PASS.

### Task 4: Wire briefing generation into CLI/runtime/docs
**Objective:** Make the feature usable from Jarvis and capture the Discord target channel in config/docs.

**Files:**
- Modify: `src/jinwang_jarvis/config.py`
- Modify: `src/jinwang_jarvis/cli.py`
- Modify: `src/jinwang_jarvis/runtime.py`
- Modify: `config/pipeline.yaml`
- Modify: `docs/playbooks.md`
- Modify: `docs/schema.md`
- Modify: `README.md` if present

**Step 1: Add CLI/config surfaces**
- Add a briefing command such as `generate-briefing`.
- Add any needed config keys for explicit Discord target and report mode.

**Step 2: Integrate runtime**
- Ensure `run-cycle` can optionally generate/update the latest briefing artifact.
- Keep wiki churn behavior intact.

**Step 3: Document usage**
- Explain the human loop: generate briefing → send to Discord → user says allow/reject → `record-feedback --create-calendar` on allow.
- Document staged backfill command for 9m/12m/.../36m.

**Step 4: Run targeted tests**
Run: `pytest -q tests/test_runtime.py tests/test_cli.py tests/test_briefing.py`
Expected: PASS.

### Task 5: Live verification in the real workspace
**Objective:** Validate on real data and perform only the next staged backfill step (9m), not a bulk jump.

**Files:**
- Read/execute in workspace only; no new files required beyond artifacts.

**Step 1: Run tests**
Run: `pytest -q`
Expected: full suite passes.

**Step 2: Generate live briefing**
Run: `PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.yaml`
Expected: JSON output with briefing artifact path and pending approval count.

**Step 3: Run next staged backfill only**
Run: `PYTHONPATH=src python3 -m jinwang_jarvis.cli backfill-next --config config/pipeline.yaml --max-months 36`
Expected: only 9m runs now because 6m is already present.

**Step 4: Reclassify/regenerate after the 9m step**
Run:
- `PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.yaml`
- `PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.yaml`
- `PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.yaml`

**Step 5: Verify results**
- Inspect candidate counts.
- Inspect whether 6m→9m introduces meaningful continuing-history items without exploding recent-important noise.
- Report the exact next staged window now recorded in checkpoints.
