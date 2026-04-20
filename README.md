# Jinwang Jarvis

A local-first mail/calendar intelligence pipeline that works well with Hermes Agent.

---

## English

### What it does
`jinwang-jarvis` watches your mail + calendar activity, scores what matters, and turns it into:
- recent important work
- continuing important work
- newly important work
- schedule recommendations
- explicit allow/reject feedback history
- recurring briefings and weekly reviews
- optional wiki memory notes for long-term synthesis

### Current status
Implemented end-to-end:
- workspace bootstrap + SQLite schema
- mail snapshot collector for inbox + sent folders
- calendar snapshot collector for Google Calendar events
- sender resolution and transparent message classifier
- proposal engine with calendar dedup + action signals
- natural-language briefing generation for Hermes/Discord approval loops
- proposal feedback recorder (`allow` / `reject`) with optional calendar creation on allow
- weekly review generator
- progressive historical backfill runner
- systemd user timer installation for reboot-safe polling resume
- reproducible CLI/bin entrypoints and tests

### Public-friendly defaults
This repository no longer requires Jinwang-specific paths or emails in tracked config.

Tracked defaults now use:
- relative workspace paths
- `discord-origin` instead of a personal channel ID
- configurable `classification.self_addresses`
- configurable `classification.work_accounts`
- a generic sender-map example

If you want to keep a private local setup, create `config/pipeline.local.yaml` and keep your personal values there.
`./scripts/install.sh` will automatically prefer `config/pipeline.local.yaml` when present.

### Quick start
```bash
git clone https://github.com/JinwangMok/jinwang-jarvis.git
cd jinwang-jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp config/pipeline.yaml config/pipeline.local.yaml
$EDITOR config/pipeline.local.yaml
```

Also create your sender map if you want sender-aware classification:
```bash
cp config/sender-map.example.md config/sender-map.md
$EDITOR config/sender-map.md
```
Then point `classification.sender_map_path` to `config/sender-map.md`.

### Typical commands
```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
```

### Approval loop
Reject example:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision reject \
  --reason-code low-value \
  --note "Not interested"
```

Allow + immediate calendar create:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other \
  --create-calendar
```

`record-feedback` automatically regenerates the next briefing artifact, so the pending approval list refreshes right away.

### systemd install
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

### More docs
- Korean setup guide: `docs/public-guide.ko.md`
- English setup guide: `docs/public-guide.en.md`
- Operational playbooks: `docs/playbooks.md`
- Cron / timer notes: `docs/cron.md`
- Data schema: `docs/schema.md`

---

## 한국어

### 이게 하는 일
`jinwang-jarvis`는 메일/캘린더 흐름을 읽어서 아래처럼 정리해주는 로컬 우선 파이프라인이야.
- 최근 중요한 일
- 계속 중요한 일
- 새로 중요해진 일
- 추천 일정
- allow/reject 피드백 이력
- 정기 브리핑 / 주간 리뷰
- 장기 기억용 위키 메모 노트(선택)

### 이제 퍼블릭하게 쓸 수 있게 바뀐 점
이제 추적되는 기본 설정에는 아래가 안 박혀 있어:
- 개인 절대경로
- 개인 Discord 채널 ID
- 특정 개인 이메일 하드코딩

대신 아래를 설정으로 바꿨다:
- `classification.self_addresses`
- `classification.work_accounts`
- 상대경로 기반 workspace/wiki
- 일반화된 sender map 예시

개인 실사용 설정은 `config/pipeline.local.yaml`에 두면 되고,
`scripts/install.sh`는 이 파일이 있으면 자동으로 그걸 우선 사용해.

### 빠른 시작
```bash
git clone https://github.com/JinwangMok/jinwang-jarvis.git
cd jinwang-jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp config/pipeline.yaml config/pipeline.local.yaml
$EDITOR config/pipeline.local.yaml
```

sender map도 필요하면:
```bash
cp config/sender-map.example.md config/sender-map.md
$EDITOR config/sender-map.md
```
그 다음 `classification.sender_map_path`를 `config/sender-map.md`로 맞추면 돼.

### 자주 쓰는 명령
```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback --config config/pipeline.local.yaml --proposal-id <proposal_id> --decision reject --reason-code low-value --note "관심없음"
```

### 자동 실행 설치
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```
