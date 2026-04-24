# Watch Pipeline Redesign: Codex Adjudication + X Mandatory Layer

> 목적: 외부 핫이슈 트래커의 남은 구현 단계를 사용자 수정사항에 맞춰 전면 재설계한다.

## 1. 사용자 수정사항

이번에 반영해야 하는 핵심 교정은 두 가지다.

1. **GPT adjudication 구현 경로 수정**
- 오답: OpenAI API key 직접 호출
- 정답: **Codex CLI에 정형화된 템플릿 질의**를 던져 JSON 판단을 받는 방식
- 이유:
  - 별도 API key 의존을 줄임
  - 이미 Codex CLI가 작업 환경에 있음
  - Hermes의 코딩/에이전트 운영 방식과 더 잘 맞음

2. **X(Twitter) 필수화**
- 오답: X를 phase-2 optional source로 미룸
- 정답: **핫이슈 지표의 핵심 reaction layer로 X를 기본 포함**
- 이유:
  - 리트윗/좋아요/답글/인용은 실제 이슈 상승을 반영하는 강력한 신호
  - official post 이후의 확산을 가장 빠르게 보여줌

## 2. 새 아키텍처 원칙

### 2.1 Adjudication engine
핫이슈 판정 엔진 우선순위:
1. **Codex CLI structured judgment**
2. heuristic fallback

즉 `gpt-5.4` / `gpt-5.5` 는 여전히 판단 모델이지만,
**호출 경로는 Codex CLI** 로 통일한다.

### 2.2 Source layer 우선순위
1. official-origin
2. **X reaction layer**
3. GeekNews / HN / Reddit reaction layer
4. analysis layer (SemiAnalysis, HPCwire 등)
5. HTML fallback origins

### 2.3 LinkedIn 위치 재조정
LinkedIn은 여전히 가치 있지만,
- X보다 우선순위가 낮고
- scraping friction이 높으므로
**X 뒤의 확장군**으로 둔다.

## 3. Codex adjudication 설계

### 3.1 입력 템플릿
Codex CLI에는 strict JSON-only 템플릿을 던진다.
입력 내용:
- canonical title
- company tag
- signal_count
- unique_source_count
- engagement_score
- reaction_score
- origin/reaction 구분
- 규칙 목록

### 3.2 기대 출력
```json
{
  "is_true_hot_issue": true,
  "importance_score_adjusted": 0.91,
  "momentum_score_adjusted": 0.42,
  "heat_level": "high",
  "judgment_reason": "...",
  "official_signal_importance": "...",
  "community_reaction_state": "...",
  "should_alert_now": true
}
```

### 3.3 실패 처리
- codex executable 없음
- codex 실행 실패
- stdout JSON 파싱 실패

이 경우:
- watch cycle 중단 금지
- heuristic fallback 사용
- `engine=heuristic-fallback`

## 4. X mandatory layer 설계

### 4.1 X의 역할
X는 단순 추가 소스가 아니라 **핫이슈 상승 감지의 핵심 반응층**이다.

주요 신호:
- repost/retweet count
- like count
- quote count
- reply count
- 특정 계정군의 동시 언급

### 4.2 추적 대상
#### origin-adjacent accounts
- OpenAI
- Anthropic
- Google / Google Cloud / DeepMind
- Meta AI
- NVIDIA
- Microsoft / Azure / AWS
- Databricks / Hugging Face / Cloudflare
- Samsung / SK hynix

#### reaction-amplifier accounts
- 주요 AI 인플루언서
- infra/semiconductor 업계 계정
- selected media / analysts

### 4.3 구현 경로
권장:
- `x-cli` 또는 `xurl` 기반 공식 API 경로
- 계정/키워드 allowlist 기반 수집

필드:
- post id
- author handle
- text
- created_at
- retweet/repost count
- reply count
- like count
- quote count
- referenced origin URL or title hints

### 4.4 X 없이 생기는 문제
질문: 왜 X를 미루면 안 되나?
답:
- 공식 발표 직후의 확산 속도를 놓침
- HN/GeekNews보다 빠른 반응층 부재
- momentum_score가 느려짐

따라서 X는 optional이 아니라 **core reaction source** 로 재분류한다.

## 5. 남은 구현 단계 재설계

### Phase A — adjudication 경로 수정
1. watch.py에서 OpenAI direct API 호출 제거
2. Codex CLI JSON adjudication 함수로 교체
3. heuristic fallback 유지
4. 관련 테스트 추가

### Phase B — X reaction ingestion 추가
1. `watch_sources`에 X source class/schema 반영
2. X account/feed seed 추가
3. X 수집기 구현 (`x-cli`/공식 API 경로)
4. retweet/like/reply/quote를 engagement 모델에 반영
5. 테스트 추가

### Phase C — cross-source linking 강화
1. official-origin ↔ X reaction 연결
2. official-origin ↔ HN/GeekNews/Reddit 연결
3. same-title / same-URL / same-company / same-time-window 규칙 정교화
4. 테스트로 issue explosion 억제

### Phase D — relevance prefilter
1. AI/Cloud relevance 필터 추가
2. 저신호 generic PR 제거
3. adjudication 대상 issue 수 줄이기
4. 테스트 추가

### Phase E — HTML fallback hardening
1. Anthropic
2. Google Cloud
3. Meta AI
4. Databricks
5. Samsung / Samsung Semiconductor

site-specific selector or extraction rules 추가

### Phase F — reporting quality
1. why-now formatting 강화
2. official vs reaction 구분 서술
3. 1시간 전 대비 증가량 명시
4. daily digest / hourly alert 정제

## 6. 실제 코드 변경 우선순위

다음 코드 작업 순서 권장:
1. `watch.py` adjudication refactor to Codex CLI
2. `tests/test_watch.py` adjudication fallback tests
3. X source seed YAML 추가
4. X fetcher 구현
5. dedup 강화
6. HTML fallback hardening

## 7. source registry 재분류

### core origin
- OpenAI RSS
- Google Blog RSS
- DeepMind RSS
- NVIDIA RSS
- IBM RSS
- Apple RSS
- SK hynix RSS
- MS/Azure/AWS RSS
- HF/Cloudflare/Together/Broadcom 등

### core reaction
- **X/Twitter**
- Hacker News
- GeekNews
- Reddit

### analysis
- SemiAnalysis
- HPCwire

## 8. HPCwire / SemiAnalysis 위치

- **SemiAnalysis**: analysis layer로 즉시 사용 가치 높음
- **HPCwire**: anti-bot 때문에 staged 유지

즉, X가 core reaction, SemiAnalysis가 analysis 강화축, HPCwire는 staged 분석축이다.

## 9. 최종 판단

질문:
핫이슈를 가장 빨리/정확히 보려면 무엇이 먼저인가?

답:
1. Codex adjudication 경로 수정
2. X 반응층 추가
3. dedup/relevance prefilter 강화

즉 다음 구현의 제1 우선순위는
- **OpenAI API 제거 → Codex CLI adjudication 전환**
- **X mandatory core source 추가**
이다.
