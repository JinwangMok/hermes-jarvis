# Watch Source Onboarding Skill Design

> 목적: 사용자가 나중에 `HPCwire`, `SemiAnalysis`, 특정 회사 블로그, 분석 매체, 커뮤니티 피드 등을 자연어로 추가 요청하면, Hermes가 안전하게 source를 탐색/검증/등록할 수 있게 하는 skill과 로직을 설계한다.

## 1. 왜 별도 skill이 필요한가

질문:
왜 그냥 `watch_sources` 테이블에 row 하나 더 넣으면 안 되는가?

답:
새 source 추가는 단순 DB insert가 아니라 다음 판단을 포함한다.
- 이 source는 official-origin 인가, reaction 인가, analysis 인가?
- RSS/API가 있는가?
- anti-bot risk는 어느 정도인가?
- browser가 필요한가?
- 바로 production enable 가능한가, staged만 해야 하는가?

즉 이건 **source onboarding workflow** 이다.

## 2. skill 목표

사용자가 예를 들어:
- "HPCwire 추가해줘"
- "semianalysis도 넣어줘"
- "이 회사 뉴스룸도 감시해줘"
- "이 URL이 source로 쓸 만한지 봐줘"
라고 말했을 때, skill이 아래를 자동 수행해야 한다.

1. 후보 source 정보 수집
2. RSS/Atom/API 우선 탐색
3. HTML fallback 필요 여부 판정
4. 실제 접근 검증
5. structured source YAML 초안 작성
6. dry-run validation
7. staged/enabled 여부 결정

## 3. 권장 skill 이름

- `watch-source-onboarding`

## 4. 입력 계약

### 최소 입력
- `display_name`
- `candidate_urls[]`

### 선택 입력
- `company_tag`
- `source_role_hint`  # official-origin | reaction | analysis
- `source_class_hint` # company | media | community | analysis
- `topic_tags[]`
- `notes`

## 5. 출력 계약

### 5.1 사용자에게 보여줄 결과
- canonical source URL
- ingest strategy (`rss|atom|api|html`)
- validation result (`verified|partial|blocked`)
- anti-bot risk
- production enable recommendation

### 5.2 파일 결과
- `config/watch-sources/user/<source-id>.yaml`

### 5.3 선택적 DB 반영
- `watch_sources` staged row upsert

## 6. skill 실행 절차

### Step 1. source role 추정
규칙:
- 회사/뉴스룸/블로그 -> `official-origin`
- GeekNews/HN/Reddit 같은 재배포/토론층 -> `reaction`
- SemiAnalysis/HPCwire 같은 해설/산업분석 -> `analysis`

### Step 2. 표면 탐색
우선순위:
1. RSS/Atom
2. JSON API
3. HTML listing page
4. article detail scrape

### Step 3. 실제 검증
검증 항목:
- HTTP status
- redirect 여부
- content-type
- browser access 가능 여부
- bot challenge 여부
- feed 본문 구조 존재 여부

### Step 4. ingest strategy 결정
- `rss` / `atom` / `api` 가능하면 그것이 canonical
- feed가 없고 listing page만 안정적이면 `html`
- anti-bot가 심하면 `blocked` 또는 `partial`

### Step 5. source YAML 생성
예시:

```yaml
source_id: semianalysis-feed
DISPLAY_NAME: SemiAnalysis
company_tag: null
source_class: analysis
source_role: analysis
base_url: https://semianalysis.com/
feed_url: https://semianalysis.com/feed/
html_list_url: null
ingest_strategy: rss
poll_minutes: 60
enabled: false
validation_status: verified
anti_bot_risk: low
browser_required: false
priority_weight: 0.7
reaction_weight: 0.6
cooldown_minutes: 60
topic_tags:
  - semiconductor
  - gpu
  - datacenter
validation_notes:
  - feed reachable over HTTP 200
  - suitable as analysis-layer source
```

## 7. 상태 머신

새 source는 다음 상태를 거친다.
- `discovered`
- `validated`
- `staged`
- `enabled`
- `suppressed`

규칙:
- `verified + anti_bot_risk low` 면 `enabled` 후보
- `partial + anti_bot_risk medium/high` 면 `staged`
- `blocked` 면 `suppressed`

## 8. 권장 CLI 연동

- `watch-sources discover --url <url>`
- `watch-sources validate --source-file <yaml>`
- `watch-sources add --source-file <yaml> --stage`
- `watch-sources promote --source-id <id>`
- `watch-sources disable --source-id <id>`

## 9. 파일/디렉터리 구조

```text
config/watch-sources/
  official/
  reaction/
  analysis/
  user/
```

이유:
- built-in 과 user-added 분리
- source role별 리뷰 용이
- Git diff 가독성 좋음

## 10. 코드 설계 제안

### 새 파일
- `src/jinwang_jarvis/watch_sources.py`
- `tests/test_watch_sources.py`

### 역할
`watch_sources.py`:
- source discovery
- feed detection
- URL canonicalization
- YAML generation
- validation report generation

## 11. acceptance 질문

source를 추가할 때 항상 세 가지를 물어야 한다.
1. 이 source는 **origin** 인가, **reaction** 인가, **analysis** 인가?
2. 이 source는 **지속 수집 가능** 한가?
3. 이 source는 **바로 production enable** 할 만큼 안정적인가?

이 질문에 답하지 못하면, source는 staged에 머물러야 한다.

## 12. 구체 사례

### HPCwire
- role: analysis
- value: 높음
- current status: browser challenge + HTTP 403
- recommendation: `validation_status=partial`, `enabled=false`, `staged`

### SemiAnalysis
- role: analysis
- value: 매우 높음
- current status: feed reachable
- recommendation: `validation_status=verified`, `enabled=true` 후보

## 13. 최종 권장

핫이슈 트래커가 장기적으로 커지려면,
source 추가를 코드 수정이 아니라 **skill-driven onboarding workflow** 로 만들어야 한다.

즉 앞으로의 목표는:
- source registry 확장
- source onboarding 자동화
- anti-bot/validation 상태 추적
- user-added source 지속 관리

이 네 가지다.
