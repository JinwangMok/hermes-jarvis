# Hot Issue + Main Company Watch Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a separate external hot-issue tracker to `jinwang-jarvis` that monitors AI/Cloud hot issues and major-company blog/news updates on an hourly cycle, uses `gpt-5.4` or `gpt-5.5` as the issue-judgment model, tracks whether each signal becomes more or less important over time, and reports only genuinely rising/important issues to the existing Discord channel.

**Architecture:** Keep this system fully separate from the mail lane. Add a dedicated `external_watch` pipeline backed by SQLite tables and lightweight fetchers. Collect raw signals from stable public sources first, normalize them, map them into durable **topics/themes** and evolving **issue stories**, compute hour-over-hour momentum deltas, then ask `gpt-5.4`/`gpt-5.5` to judge whether the issue is truly important. Official company posts are first-class hot-issue signals by themselves. Community reaction to those official posts is tracked as a separate reaction layer, not conflated with the original issue event.

**Tech Stack:** Python, SQLite, existing Jarvis CLI/runtime/config, RSS/API fetchers, cron jobs, and Codex GPT-5.4 / GPT-5.5 for final issue adjudication.

---

## 1. Product intent

The user clarified four hard rules:

1. **This is not mail.**
   - Do not model it like inbox triage.
   - Do not reuse mail recommendation semantics.

2. **The watch cycle is hourly.**
   - Default polling and scoring cadence: **1 hour**.

3. **The final issue judgment uses a model.**
   - `gpt-5.4` or `gpt-5.5` should evaluate whether a signal is a “real” hot issue.

4. **Do not alert on “new clusters.”**
   - Here, “cluster” is closer to a **topic/theme category**, not “new duplicate group detected.”
   - The system should instead track whether a signal is becoming materially hotter than it was **one hour ago**.

This means the system must answer three questions every hour:
1. Is this signal truly about **AI/Cloud**?
2. Is this signal **important in itself**?
3. Is this signal becoming **more important than it was one hour ago**?

So the system separates:
- **raw signal ingestion**
- **topic/theme classification**
- **issue-story tracking over time**
- **LLM adjudication of true hotness**
- **hour-over-hour momentum/delta evaluation**
- **delivery**

## 2. Core conceptual model

### 2.1 Separate concepts: topic vs issue vs reaction

The previous design used “cluster” too loosely. Replace it with these terms:

#### A. Topic / theme
Broad category only.
Examples:
- `ai-models`
- `agents`
- `cloud`
- `gpu`
- `semiconductor`
- `datacenter`
- `policy`

This is **not** something to alert on by itself.

#### B. Issue story
A concrete evolving thing in the world.
Examples:
- `Anthropic released Opus-4.7`
- `OpenAI launched new enterprise API tier`
- `Nvidia announced Blackwell server availability`
- `SK hynix disclosed new HBM roadmap`

This is the main tracked unit.

#### C. Reaction signal
How community/news reacts to an issue story.
Examples:
- Hacker News discussion on the Anthropic post
- GeekNews repost/summary of the launch
- Reddit thread sentiment around the announcement

This is **not the same issue as the official post itself**. It is a second layer attached to that issue story.

### 2.2 Three-lane model
- **Operational lane:** mail tasking/approval
- **Knowledge lane:** All Mail long-term memory
- **External watch lane:** AI/Cloud issue and company watch

Keep the external watch lane isolated from mail semantics and tables.

Related source-registry document:
- `docs/plans/2026-04-23-starter-source-registry.md` — tested starter company/source list with actual verified URLs and collection strategy notes.
- `docs/plans/2026-04-23-watch-source-onboarding-skill.md` — design for later user-driven source addition, validation, staging, and promotion.
- `docs/plans/2026-04-23-watch-redesign-codex-x.md` — corrected redesign: Codex CLI adjudication path and X(Twitter) as a mandatory core reaction layer.

## 3. In-scope source families

### 3.1 Official company/blog/news sources
These are first-class signals on their own.

Target companies include:
- Anthropic
- OpenAI
- Google
- Google Cloud
- DeepMind
- Meta / Meta AI
- Nvidia
- IBM / IBM Research
- Apple / Apple ML / Apple Newsroom
- Samsung / Samsung Research / Samsung Semiconductor / Samsung Newsroom
- SK hynix
- Microsoft
- AWS
- Databricks
- Hugging Face
- Cloudflare
- Oracle Cloud
- Snowflake
- AMD
- TSMC

Rule:
- **A new official post can itself be a hot issue even before community pickup.**

### 3.2 Community/news aggregators
These are used to measure spread, amplification, and reaction.
- GeekNews RSS
- Hacker News API / Algolia
- Reddit RSS/JSON on selected subreddits

### 3.3 Phase-2 social/news
- X/Twitter official API if credentials exist
- LinkedIn only through reliable public/newsroom/email-backed paths

### 3.4 Out of scope for v1
- login-dependent scraping
- fragile browser automation
- full LinkedIn scraping
- websocket streaming

## 4. Polling cadence

### 4.1 Default cadence
Set the external tracker cadence to:
- **every 1 hour** for collection + scoring + adjudication

### 4.2 Why 1 hour is correct
Ask: do we need minute-level latency for company blog/news tracking? Usually no.

Hourly cadence is better because it allows:
- enough time for secondary pickup signals to appear
- direct comparison with the prior hour
- lower noise and lower API/fetch cost
- a meaningful “is this growing?” calculation

### 4.3 Separate cron model
Do not piggyback on the 5-minute mail pipeline.

Recommended jobs:
- **hourly hot-issue cycle**: collect -> map -> compare vs last hour -> LLM judge -> alert if needed
- **daily summary cycle**: top issues / top companies / biggest momentum gainers

## 5. Data model

Add these tables in `src/jinwang_jarvis/bootstrap.py`.

### 5.1 `watch_sources`
One row per official blog/feed/community source.
- `source_id` TEXT PK
- `source_type` TEXT  # official-blog | newsroom | geeknews | hackernews | reddit | x | linkedin
- `display_name` TEXT
- `base_url` TEXT
- `feed_url` TEXT NULL
- `company_tag` TEXT NULL
- `topic_tags_json` TEXT
- `poll_minutes` INTEGER
- `enabled` INTEGER
- `priority_weight` REAL
- `created_at` TEXT
- `updated_at` TEXT

### 5.2 `watch_signals`
One raw normalized signal per fetched post/story/thread.
- `signal_id` TEXT PK
- `source_id` TEXT
- `source_type` TEXT
- `signal_kind` TEXT  # official-post | media-post | aggregator-post | community-thread | reaction-thread
- `company_tag` TEXT NULL
- `external_id` TEXT NULL
- `title` TEXT
- `url` TEXT
- `author` TEXT NULL
- `summary_text` TEXT NULL
- `published_at` TEXT
- `collected_at` TEXT
- `engagement_json` TEXT
- `topic_tags_json` TEXT
- `entity_tags_json` TEXT
- `language` TEXT NULL
- `canonical_key` TEXT
- `content_hash` TEXT
- `raw_payload_json` TEXT

### 5.3 `watch_topics`
Broad topic/theme registry. Not alert units.
- `topic_id` TEXT PK
- `topic_name` TEXT
- `description` TEXT NULL
- `keywords_json` TEXT
- `entity_hints_json` TEXT
- `created_at` TEXT
- `updated_at` TEXT

### 5.4 `watch_issue_stories`
Main tracked issue unit.
- `issue_id` TEXT PK
- `story_key` TEXT UNIQUE
- `canonical_title` TEXT
- `canonical_summary` TEXT NULL
- `primary_company_tag` TEXT NULL
- `topic_ids_json` TEXT
- `entity_tags_json` TEXT
- `origin_signal_id` TEXT NULL
- `origin_kind` TEXT  # official-origin | community-origin | mixed-origin
- `first_seen_at` TEXT
- `last_seen_at` TEXT
- `current_importance_score` REAL
- `current_momentum_score` REAL
- `current_heat_level` TEXT  # low | medium | high | critical
- `report_status` TEXT  # unseen | watching | alerted | cooling | suppressed
- `last_reported_at` TEXT NULL

### 5.5 `watch_issue_signals`
Attach many raw signals to one issue story.
- `issue_id` TEXT
- `signal_id` TEXT
- `role` TEXT  # origin | corroboration | amplification | reaction
- PK `(issue_id, signal_id)`

### 5.6 `watch_issue_snapshots`
Hourly snapshots for delta tracking.
- `snapshot_id` TEXT PK
- `issue_id` TEXT
- `snapshot_hour` TEXT
- `signal_count` INTEGER
- `official_signal_count` INTEGER
- `community_signal_count` INTEGER
- `unique_source_count` INTEGER
- `engagement_score` REAL
- `reaction_score` REAL
- `importance_score` REAL
- `momentum_score` REAL
- `heat_level` TEXT
- `llm_judgment_json` TEXT

### 5.7 `watch_reports`
Audit trail.
- `report_id` TEXT PK
- `generated_at` TEXT
- `report_kind` TEXT  # hourly-hot-issues | daily-watch-digest | company-digest
- `issue_ids_json` TEXT
- `artifact_file` TEXT
- `delivered_channel` TEXT

## 6. Config surface

Extend `config/pipeline.yaml` and `config/pipeline.local.yaml`:

```yaml
watch:
  enabled: true
  snapshot_dir: data/watch
  default_poll_minutes: 60
  adjudicator_model: gpt-5.4
  fallback_model: gpt-5.5
  importance_alert_threshold: 0.82
  momentum_alert_threshold: 0.18
  digest_threshold: 0.60
  recency_hours: 24
  story_similarity: 0.84
  compare_window_hours: 1
  target_companies:
    - anthropic
    - openai
    - google
    - meta
    - nvidia
    - ibm
    - apple
    - samsung
    - sk-hynix
  subreddits:
    - LocalLLaMA
    - singularity
    - MachineLearning
    - artificial
    - cloud
    - datacenter
  enable_sources:
    official_blogs: true
    geeknews: true
    hackernews: true
    reddit: true
    x: false
    linkedin: false
```

Critical rule:
- this `watch:` block must remain operationally independent from mail settings.

## 7. Fetch strategy by source

### 7.1 Stable-first rule
Ask: does the source have a stable public feed/API? If yes, use it first.

### 7.2 Official blogs/newsrooms
Priority 1.
- prefer RSS/Atom
- known newsroom feed URLs second
- HTML fallback only for curated hard cases

These signals get strong base importance even with no community confirmation.

### 7.3 GeekNews
Use RSS-first.
Purpose:
- Korean tech-community pickup
- secondary validation / amplification

### 7.4 Hacker News
Use official API or Algolia.
Purpose:
- global developer/infra/AI community attention
- engagement signal via points/comments

### 7.5 Reddit
Use selected subreddit RSS/JSON.
Purpose:
- community attention and debate layer
- useful for sentiment/reaction, not origin authority

### 7.6 X (phase 2)
Use only official API.
Purpose:
- fast pickup / spread detection
- author/account-based importance boosts

### 7.7 LinkedIn (phase 2.5)
Treat carefully.
Purpose:
- company hiring/enterprise/product posture
- but do not let brittle scraping define v1

## 8. Topic and entity model

### 8.1 Topic/theme tags
These are classification labels, not alert units.
- `ai-models`
- `agents`
- `cloud`
- `gpu`
- `semiconductor`
- `datacenter`
- `robotics`
- `multimodal`
- `open-source`
- `policy`
- `funding`
- `launch`
- `partnership`
- `benchmark`
- `inference`

### 8.2 Canonical entity/company tags
- `anthropic`
- `openai`
- `google`
- `google-cloud`
- `deepmind`
- `meta`
- `nvidia`
- `ibm`
- `apple`
- `samsung`
- `samsung-semiconductor`
- `sk-hynix`
- `aws`
- `microsoft`
- `databricks`
- `huggingface`
- `cloudflare`
- `amd`
- `tsmc`

### 8.3 Keyword logic
Implement transparent rule maps in `src/jinwang_jarvis/watch.py`.

Examples:
- `claude`, `opus`, `sonnet`, `haiku` -> `anthropic`
- `gpt`, `openai api`, `operator`, `sora` -> `openai`
- `gemini`, `vertex ai`, `tpu`, `deepmind` -> `google`
- `llama`, `meta ai` -> `meta`
- `blackwell`, `cuda`, `dgx`, `nvlink` -> `nvidia`
- `hbm`, `dram`, `foundry`, `packaging` -> `semiconductor`

## 9. Story mapping and temporal tracking

### 9.1 Why issue stories matter
You do not want:
- “new topic detected” alerts
- “new duplicate group” alerts

You want:
- `Anthropic Opus-4.7` was important at 09:00
- at 10:00 it has spread to HN + GeekNews and reaction intensity increased
- therefore **its hotness increased**

So the main tracked object is an **issue story over time**.

### 9.2 Story mapping rules
Map raw signals into issue stories using:
1. same canonical URL -> same issue story candidate
2. high title similarity + same company/entity + same 48h window -> same issue story
3. official-post and community-thread can map to the same issue if the thread clearly discusses that official announcement

### 9.3 Reaction is attached, not merged blindly
Example:
- origin: official Anthropic post
- reaction: HN thread about the post
- reaction: Reddit thread criticizing benchmarks

These become separate raw signals, but one shared issue story.

The LLM should still distinguish:
- **issue importance itself**
- **reaction intensity around the issue**

## 10. Scoring model

### 10.1 Two scores, not one
Track separately:
- **importance_score**: how inherently important the issue is
- **momentum_score**: how much hotter it became vs one hour ago

### 10.2 Base importance features
Use deterministic pre-score before LLM:
- official-source bonus
- target-company bonus
- AI/Cloud topic match bonus
- launch/release/chip/product/model bonus
- unique-source count
- engagement score
- penalty for generic low-value reposts

### 10.3 Momentum features
Compare latest snapshot to previous hour:
- signal count delta
- source diversity delta
- engagement delta
- first appearance on major community source
- first appearance in Korean tech community (GeekNews)
- first major reaction wave after official post

### 10.4 Example momentum interpretation
Ask: what changed in 1 hour?
- same official blog post, no new pickup -> low momentum
- official blog post + HN thread launched + GeekNews repost + Reddit discussion started -> high momentum
- older story fading out -> negative/flat momentum

## 11. LLM adjudication with GPT-5.4 / GPT-5.5

### 11.1 Why use the model
Rule-based scoring can estimate structure, but not fully judge:
- whether a post is a genuinely meaningful AI/Cloud development
- whether the spread indicates real industry attention vs noise
- whether a company blog post is merely routine PR or actually important

### 11.2 Adjudication input package
For each candidate issue story, pass:
- canonical title
- canonical summary
- source list
- signal types (official, community, reaction)
- target company/entity tags
- engagement summary
- previous-hour snapshot
- current snapshot
- computed deltas

### 11.3 Expected model outputs
Structured JSON fields:
- `is_true_hot_issue` boolean
- `importance_score_adjusted` float
- `momentum_score_adjusted` float
- `heat_level` low|medium|high|critical
- `judgment_reason` short text
- `official_signal_importance` short text
- `community_reaction_state` short text
- `should_alert_now` boolean

### 11.4 Key judgment rules for the prompt
The model must follow these rules:
1. official company posts can be hot issues by themselves
2. community reaction is a separate lens, not the same thing as the origin event
3. alert on real importance or material hour-over-hour rise
4. do not alert simply because a new topic label appeared
5. prefer AI/Cloud significance over generic business/marketing noise

## 12. Reporting policy

### 12.1 Hourly hot-issue alert
Run every hour.

Alert when either:
- issue is inherently important enough now, or
- issue importance/momentum increased materially since last hour

Recommended rule:
- `should_alert_now=true` from the LLM
- and either `importance_score_adjusted >= threshold` or `momentum_score_adjusted >= threshold`

### 12.2 Alert payload format
For each alerted issue:
- issue title
- why it matters now
- official-source status
- reaction status summary
- 1-hour change summary
- representative links

Recommended wording blocks:
- `왜 지금 중요:`
- `공식 신호:`
- `커뮤니티 반응:`
- `1시간 전 대비:`

### 12.3 Daily digest
Once per day:
- top official company developments
- biggest momentum gainers
- strongest community reactions
- company-by-company summary

## 13. Wiki/report outputs

Add a separate watch namespace:
- `queries/jinwang-jarvis-watch/index.md`
- `queries/jinwang-jarvis-watch/hourly/latest-hot-issues.md`
- `queries/jinwang-jarvis-watch/daily/daily-YYYY-MM-DD.md`
- `queries/jinwang-jarvis-watch/companies/<company>.md`
- `queries/jinwang-jarvis-watch/issues/<issue-key>.md`

Important note:
- `issues/<issue-key>.md` is the natural place to show the time evolution of a real issue story.

## 14. Code organization

### New files
- `src/jinwang_jarvis/watch.py`
- `tests/test_watch.py`
- `tests/test_watch_cli.py`
- `docs/plans/2026-04-23-hot-issue-company-watch.md`

### Modify
- `src/jinwang_jarvis/bootstrap.py`
- `src/jinwang_jarvis/config.py`
- `src/jinwang_jarvis/cli.py`
- `src/jinwang_jarvis/runtime.py`
- `tests/test_config.py`
- `tests/test_runtime.py`
- `README.md`
- `docs/cron.md`
- `config/pipeline.yaml`

### CLI additions
- `sync-watch-sources`
- `collect-watch-signals`
- `build-watch-stories`
- `judge-watch-issues`
- `generate-watch-report`
- `run-watch-cycle`

Recommended pipeline:
- `run-watch-cycle`
  1. collect signals
  2. map to issue stories
  3. compute hourly snapshots and deltas
  4. run GPT adjudication
  5. generate artifact
  6. deliver if truly hot

## 15. Runtime and cron model

### 15.1 Main separation
Do not put watch work inside the 5-minute mail loop.

### 15.2 Recommended jobs
- **hourly watch cycle**: `every 1h`
- **daily watch digest**: once per day

### 15.3 State and dedupe
Use dedicated state tracking:
- `state/watch_report_state.json`

Track:
- last reported issue snapshot
- prior-hour issue metrics
- recently alerted issue ids
- last digest time

This supports “became hotter than 1 hour ago” logic.

## 16. TDD plan

### `tests/test_watch.py`
Add tests for:
- canonical URL normalization
- issue story mapping from official post + HN thread
- topic classification distinct from issue story identity
- official posts receiving high base importance
- reaction threads affecting momentum without overwriting origin identity
- hour-over-hour momentum increase detection
- old/noisy stories cooling down correctly

### `tests/test_watch_cli.py`
- collect command writes normalized signals
- story-building command attaches reactions correctly
- judge command stores LLM judgment JSON
- report command returns `[SILENT]` when nothing crosses importance or momentum thresholds

### `tests/test_runtime.py`
- watch cycle isolated from mail cycle failures
- watch-enabled cron/report path works independently

## 17. Stepwise implementation order

### Phase 1: schema + config
1. add `watch:` config and defaults
2. add watch tables
3. add bootstrap migrations

### Phase 2: signal collection
4. seed official company sources
5. add GeekNews/HN/Reddit fetchers
6. normalize raw signals into `watch_signals`

### Phase 3: story tracking
7. map signals into issue stories
8. create hourly snapshots
9. compute importance and momentum deltas

### Phase 4: LLM adjudication
10. add structured GPT-5.4 / GPT-5.5 judgment step
11. persist `llm_judgment_json`
12. integrate thresholds and alert decisions

### Phase 5: reporting
13. add hourly hot-issue report
14. add daily digest and company pages
15. wire hourly cron

### Phase 6: expansion
16. add X support behind feature flag
17. add LinkedIn indirect/reliable-source support

## 18. Verification commands

Run from repo root:

```bash
cd /home/jinwang/workspace/jinwang-jarvis
PYTHONPATH=src pytest -q tests/test_watch.py tests/test_watch_cli.py tests/test_config.py tests/test_runtime.py
PYTHONPATH=src python3 -m jinwang_jarvis.cli sync-watch-sources --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-watch-signals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli build-watch-stories --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli judge-watch-issues --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-watch-report --config config/pipeline.local.yaml --report-kind hourly-hot-issues
```

Live verification expectations:
- `watch_signals` rows appear
- `watch_issue_stories` rows appear
- `watch_issue_snapshots` contain hourly deltas
- official company posts survive as issue stories even without community pickup
- community reaction is attached as reaction, not mistaken as a separate origin issue unless truly independent
- report prints either hot issues or `[SILENT]`

## 19. Product decisions

### Decision A: official-source-first importance
A new official company announcement can be a hot issue on its own.

### Decision B: reaction is separate from origin
Community reaction is tracked, but it is a separate analytical layer.

### Decision C: hourly delta matters
The system must explicitly compare current state vs the prior hour.

### Decision D: topic is taxonomy, not alert unit
Topics/themes are labels. They do not trigger alerts by themselves.

### Decision E: GPT adjudication is first-class
`gpt-5.4` / `gpt-5.5` is part of the design, not a future add-on.

## 20. Main design questions to preserve

Two Socratic checks should stay in the implementation prompt:

1. **Would this still be important if nobody on HN/Reddit reacted yet?**
   - If yes, the official signal itself may justify alerting.

2. **What changed since one hour ago?**
   - If the answer is “not much,” then it may be important but not newly urgent.
   - If the answer is “pickup and reaction accelerated,” then its momentum is real.

That is the core of the tracker you asked for: not “new cluster detected,” but **real issue importance + hour-over-hour heat change**.