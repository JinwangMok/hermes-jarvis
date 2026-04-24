# Starter Source Registry Design for AI/Cloud Hot-Issue Tracker

> 목적: `jinwang-jarvis` 외부 핫이슈 트래커의 v1 starter source registry를 실제 접근 테스트 기반으로 정의한다.

## 1. 설계 원칙

핵심 질문:
1. 이 소스는 **공식 origin signal** 인가?
2. 이 소스는 **반응/reaction signal** 인가?
3. 이 소스는 **기계적으로 안정 수집** 가능한가?

따라서 source registry는 세 등급으로 나눈다.

- **Tier A — 공식 RSS/API 우선**
  - 가장 안정적
  - origin signal로 쓰기 좋음
- **Tier B — 공식 HTML fallback**
  - RSS가 없거나 불확실함
  - HTML scraper 대상
- **Tier C — reaction/community surfaces**
  - GeekNews / HN / Reddit
  - origin이 아니라 반응/확산 추적 용도

## 2. 실제 접근 테스트 결과 요약

테스트 방법:
- **HTTP 검증**: requests GET으로 status / content-type / redirect 확인
- **브라우저 검증**: Hermes browser로 실제 접근 확인

중요 관찰:
- `openai.com/news/` 본문 페이지는 브라우저에서 bot challenge가 걸렸지만, **`/news/rss.xml`는 정상 접근 가능**
- Reddit RSS는 HTTP 200이지만, 브라우저에선 **network security block**가 걸림
- Samsung Global Newsroom은 HTTP로 feed 접근은 가능했지만, 브라우저 page navigate는 불안정/abort가 있었음
- 따라서 v1은 **RSS/API 우선**, 브라우저 불안정 사이트는 browser scraping이 아니라 feed polling으로 가는 게 맞음

## 3. 추천 starter source registry

### 3.1 Tier A — 공식 origin signal용

| company/source | role | tested url | type | test result | note |
|---|---|---|---|---|---|
| Anthropic News | official-origin | `https://www.anthropic.com/news` | HTML | HTTP 200, browser OK | RSS 미발견. HTML fallback 대상 |
| OpenAI News | official-origin | `https://openai.com/news/rss.xml` | RSS | HTTP 200, browser OK | 본문 `/news/`는 bot challenge, RSS 사용 권장 |
| Google Blog | official-origin | `https://blog.google/rss/` | RSS | HTTP 200, browser OK | The Keyword |
| Google Cloud Blog | official-origin | `https://cloud.google.com/blog` | HTML | HTTP 200 | RSS 미확인. HTML fallback |
| Google DeepMind | official-origin | `https://deepmind.google/blog/rss.xml` | RSS | HTTP 200, browser OK | 안정적 |
| Meta AI Blog | official-origin | `https://ai.meta.com/blog/` | HTML | HTTP 200 | RSS 미확인. HTML fallback |
| NVIDIA Blog | official-origin | `https://blogs.nvidia.com/feed/` | RSS | HTTP 200, browser OK | 안정적 |
| IBM Research | official-origin | `https://research.ibm.com/rss` | RSS | HTTP 200, browser OK | 안정적 |
| Apple Newsroom | official-origin | `https://www.apple.com/newsroom/rss-feed.rss` | RSS/Atom | HTTP 200, browser OK | 광범위 기업 공지 |
| Apple ML Research | official-origin | `https://machinelearning.apple.com/rss.xml` | RSS/XML | HTTP 200 | 연구/ML 특화 |
| Samsung Global Newsroom | official-origin | `https://news.samsung.com/global/feed` | RSS | HTTP 200 | browser page 접근은 불안정, feed polling 권장 |
| Samsung Semiconductor News | official-origin | `https://semiconductor.samsung.com/news-events/news/` | HTML | HTTP 200 | RSS 미확인. HTML fallback |
| SK hynix Newsroom | official-origin | `https://news.skhynix.com/feed/` | RSS | HTTP 200, browser OK | 안정적 |
| Microsoft Blog | official-origin | `https://blogs.microsoft.com/feed/` | RSS | HTTP 200, browser OK | 안정적 |
| Azure Blog | official-origin | `https://azure.microsoft.com/en-us/blog/feed/` | RSS | HTTP 200, browser OK | cloud infra relevance 높음 |
| AWS ML Blog | official-origin | `https://aws.amazon.com/blogs/machine-learning/feed/` | RSS | HTTP 200, browser OK | AI/Cloud 핵심 |
| Databricks Blog | official-origin | `https://www.databricks.com/blog` | HTML | HTTP 200, browser OK | RSS 미확인. HTML fallback |
| Hugging Face Blog | official-origin | `https://huggingface.co/blog/feed.xml` | RSS | HTTP 200, browser OK | 모델/오픈소스 동향 |
| Cloudflare AI tag | official-origin | `https://blog.cloudflare.com/tag/ai/rss` | RSS | HTTP 200, browser OK | AI inference / edge / infra 관련 |

### 3.2 Tier C — core reaction/amplification signal용

| source | role | tested url | type | test result | note |
|---|---|---|---|---|---|
| GeekNews Feed | reaction | `https://feeds.feedburner.com/geeknews-feed` | Atom | HTTP 200, browser OK | 한국 반응층 |
| Hacker News Topstories | reaction | `https://hacker-news.firebaseio.com/v0/topstories.json` | JSON API | HTTP 200, browser OK | 실시간 discussion seed |
| Reddit LocalLLaMA | reaction | `https://www.reddit.com/r/LocalLLaMA/.rss` | Atom | HTTP 200, browser blocked | HTTP collector는 가능, browser scraping은 비권장 |
| X/Twitter account/timeline layer | reaction | account allowlist + official API | API | 설계상 필수, 아직 미구현 | 리트윗/답글/인용/좋아요 기반 핵심 hotness layer |

## 4. 메인 플레이어 추천 범위

v1 starter company set:
- Anthropic
- OpenAI
- Google
- Google Cloud
- Google DeepMind
- Meta AI
- NVIDIA
- IBM Research
- Apple
- Samsung
- Samsung Semiconductor
- SK hynix
- Microsoft
- Azure
- AWS
- Databricks
- Hugging Face
- Cloudflare

질문:
왜 Oracle/Snowflake/AMD/TSMC는 starter set에서 뒤로 미뤘는가?
- relevance는 높지만,
- **초기 운영 안정성** 기준으로는 위 18개가 더 실용적이고,
- HTML fallback 비중이 커질수록 유지보수 비용이 올라가기 때문

따라서 Oracle/Snowflake/AMD/TSMC는 **phase-1.5 확장군**으로 두는 것이 맞다.

## 5. source type 정책

### A. RSS/API available
이 경우 원칙:
- RSS/API를 canonical ingest surface로 사용
- HTML scraping은 하지 않음

대상:
- OpenAI News RSS
- Google Blog RSS
- DeepMind RSS
- NVIDIA RSS
- IBM RSS
- Apple Newsroom RSS
- Apple ML RSS
- Samsung Global RSS
- SK hynix RSS
- Microsoft RSS
- Azure RSS
- AWS ML RSS
- Hugging Face RSS
- Cloudflare AI RSS
- GeekNews feed
- HN API
- Reddit RSS

### B. HTML fallback required
이 경우 원칙:
- list page scrape만 수행
- article detail page scrape는 필요 시에만
- selector drift 감시 필요

대상:
- Anthropic News
- Google Cloud Blog
- Meta AI Blog
- Samsung Semiconductor News
- Databricks Blog

## 6. registry schema 제안

`watch_sources` starter seed에 아래 필드를 권장:

- `source_id`
- `display_name`
- `company_tag`
- `source_role`  # official-origin | reaction
- `source_type`  # rss | atom | api | html
- `base_url`
- `feed_url`
- `html_list_url`
- `poll_minutes`  # 60
- `enabled`
- `priority_weight`
- `reaction_weight`
- `selector_json`  # html fallback only
- `notes`

예시:

```yaml
- source_id: openai-news
  display_name: OpenAI News RSS
  company_tag: openai
  source_role: official-origin
  source_type: rss
  base_url: https://openai.com/news/
  feed_url: https://openai.com/news/rss.xml
  html_list_url: null
  poll_minutes: 60
  enabled: true
  priority_weight: 1.0
  reaction_weight: 0.0
  selector_json: null
  notes: official RSS works even though /news page may trigger bot challenge
```

## 7. 운영 권장안

### 7.1 v1 최소 안정 구성
먼저 켜야 할 것:
- OpenAI News RSS
- Google Blog RSS
- Google DeepMind RSS
- NVIDIA RSS
- IBM RSS
- Apple Newsroom RSS
- SK hynix RSS
- Microsoft RSS
- Azure RSS
- AWS ML RSS
- Hugging Face RSS
- Cloudflare AI RSS
- GeekNews Feed
- HN API
- X/Twitter account/timeline layer (core reaction)

이 구성만으로도:
- 공식 발표 포착
- 글로벌 developer 반응
- 한국 커뮤니티 반응
- 실시간 X 확산 지표
을 모두 볼 수 있다.

### 7.2 v1 확장 구성
추가:
- Anthropic HTML
- Google Cloud HTML
- Meta AI HTML
- Samsung Global RSS
- Samsung Semiconductor HTML
- Databricks HTML
- Reddit RSS

이 확장군은 가치가 높지만, 일부는 browser stability / HTML drift 리스크가 있다.

## 8. 브라우저 테스트에서 확인된 특이사항

- **Anthropic**: 브라우저 정상, 최신 글 노출 확인 (`Introducing Claude Opus 4.7` 등)
- **OpenAI**: `/news/`는 browser challenge, 하지만 `rss.xml`은 브라우저 정상
- **Databricks**: 브라우저 정상, 최신 글 목록 확인
- **Samsung Global**: feed는 HTTP 정상, browser page 접근은 불안정
- **Reddit**: RSS는 HTTP 정상, browser는 차단

이건 곧 무엇을 의미하나?
- source registry는 단순 URL 목록이 아니라,
- **수집 표면별 신뢰도/접근전략까지 포함해야 한다**는 뜻이다.

## 9. 최종 starter registry 판단

### 바로 seed해도 되는 high-confidence sources
- OpenAI News RSS
- Google Blog RSS
- Google DeepMind RSS
- NVIDIA RSS
- IBM RSS
- Apple Newsroom RSS
- Apple ML RSS
- SK hynix RSS
- Microsoft RSS
- Azure RSS
- AWS ML RSS
- Hugging Face RSS
- Cloudflare AI RSS
- GeekNews feed
- HN API

### fallback 정책이 필요한 medium-confidence sources
- Anthropic News HTML
- Google Cloud Blog HTML
- Meta AI Blog HTML
- Samsung Global RSS
- Samsung Semiconductor HTML
- Databricks Blog HTML
- Reddit RSS

## 10. phase-1.5 확장군

추가로 더 조사한 AI/Cloud infra 관련 후보와 테스트 결과:

| source | role | tested url | type | test result | note |
|---|---|---|---|---|---|
| Broadcom News | official-origin | `https://news.broadcom.com/feed` | RSS | HTTP 200 | feed 확인됨 |
| Cisco Newsroom Cloud | official-origin | `https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json?feed=cloud` | RSS-like feed endpoint | 브라우저 RSS 피드 목록 페이지 확인 | cloud 전용 feed가 실용적 |
| Palo Alto Networks Blog | official-origin | `https://www.paloaltonetworks.com/blog/feed/` | RSS | HTTP 200 | security/AI infra 경계 이슈용 |
| Together AI Blog | official-origin | `https://www.together.ai/blog/rss.xml` | RSS | HTTP 200 | feed 발견/검증 완료 |
| SemiAnalysis | analysis/reaction | `https://semianalysis.com/feed/` | RSS | HTTP 200 | 반도체/AI infra 분석층으로 매우 유용 |
| HPCwire | analysis/reaction | `https://www.hpcwire.com/feed/` | RSS | HTTP 403, browser challenge | 가치 높지만 현재 직접 수집 불안정 |
| Snowflake Blog | official-origin | `https://www.snowflake.com/en/blog/` | HTML | HTTP 200 | feed 미확인, HTML fallback 후보 |
| Groq Blog/Newsroom | official-origin | `https://groq.com/blog`, `https://groq.com/newsroom` | HTML | HTTP 200 | RSS 미확인 |
| Cerebras Blog | official-origin | `https://www.cerebras.ai/blog` | HTML | HTTP 200 | RSS 미확인 |
| Mistral News | official-origin | `https://mistral.ai/news` | HTML | HTTP 200 | RSS 미확인 |
| Cohere Blog | official-origin | `https://cohere.com/blog` | HTML | HTTP 200 | RSS 미확인 |
| SambaNova Blog | official-origin | `https://sambanova.ai/resources/tag/blog` | HTML | HTTP 200 | redirected resource page |

판단:
- **Broadcom / Palo Alto / Together / SemiAnalysis** 는 실제 starter 확장 가치가 높다.
- **HPCwire** 는 가치가 높지만, 현재는 anti-bot 때문에 canonical source로 넣기 어렵다.
- **Snowflake / Groq / Cerebras / Mistral / Cohere / SambaNova** 는 HTML fallback 후보로 둘 수 있다.

## 11. 사용자 추가 source onboarding 로직 설계

질문:
나중에 사용자가 `HPCwire`, `SemiAnalysis`, 혹은 전혀 새 사이트를 추가하고 싶을 때 어떻게 할까?

정답은 수동 코드 수정이 아니라, **source onboarding pipeline** 을 만드는 것이다.

### 11.1 목표
사용자가 자연어로:
- "HPCwire 추가해줘"
- "semianalysis도 source로 넣어줘"
- "이 회사 블로그도 감시해줘"
라고 말하면, Hermes가 아래를 자동 수행할 수 있어야 한다.

1. source role 판정
   - official-origin / reaction / analysis
2. 수집 표면 탐색
   - RSS/Atom/API 우선
   - 없으면 HTML fallback
3. 실제 접근 테스트
   - HTTP
   - 필요 시 browser
4. registry candidate 생성
5. dry-run fetch 검증
6. `watch_sources` 또는 seed YAML에 반영

### 11.2 제안 CLI
나중 구현용 CLI:
- `watch-sources discover --url <url>`
- `watch-sources validate --source-file <yaml>`
- `watch-sources add --source-file <yaml>`
- `watch-sources list`
- `watch-sources disable --source-id <id>`

### 11.3 제안 파일 구조
```text
config/watch-sources/
  official/
  reaction/
  user/
```

예:
- `config/watch-sources/official/openai-news.yaml`
- `config/watch-sources/reaction/geeknews.yaml`
- `config/watch-sources/user/semianalysis.yaml`

이 구조의 장점:
- 코드 수정 없이 source 추가 가능
- Git 관리 용이
- user-added source와 built-in source 분리 가능

### 11.4 source onboarding skill 설계
미리 별도 Hermes skill로 설계해두는 게 맞다.

권장 skill 이름:
- `watch-source-onboarding`

이 skill의 입력:
- 회사명 또는 매체명
- 후보 URL 1개 이상
- source role 힌트(official/reaction/analysis)

이 skill의 절차:
1. 후보 URL 접근 테스트
2. RSS/Atom/API 링크 자동 탐색
3. HTML fallback 필요 여부 판정
4. anti-bot / browser-block 기록
5. canonical source YAML 초안 생성
6. dry-run validation 실행
7. 성공 시 `config/watch-sources/user/*.yaml` 저장

### 11.5 source YAML schema 확장
기존 schema에 아래를 추가 권장:
- `source_class`  # company | media | community | analysis
- `source_role`   # official-origin | reaction | analysis
- `ingest_strategy`  # rss | atom | api | html
- `validation_status`  # verified | partial | blocked
- `validation_notes`
- `browser_required` boolean
- `anti_bot_risk`  # low | medium | high
- `cooldown_minutes`

### 11.6 onboarding acceptance rule
새 source는 바로 production enable 하지 말고:
1. `discovered`
2. `validated`
3. `staged`
4. `enabled`
5. `suppressed`
상태를 거치게 하는 것이 맞다.

특히 HPCwire 같은 사이트는:
- relevance는 높지만
- 현재 anti-bot risk가 높으므로
- `validated=partial`, `enabled=false` 로 저장하는 편이 안전하다.

## 12. 다음 단계

다음 질문:
1. v1 seed를 **high-confidence only**로 갈까?
2. 아니면 Anthropic/Meta/Databricks/Samsung/Broadcom/PaloAlto/Together/SemiAnalysis까지 포함한 **expanded starter set**으로 갈까?
3. 그리고 source onboarding skill 설계 문서를 별도로 분리할까?

내 추천:
- **seed 1차 = high-confidence only**
- **seed 2차 = medium-confidence + phase-1.5 확장군 추가**
- **skill 설계는 별도 문서로 분리**

이유:
- 시간당 1회 핫이슈 추적에서 가장 중요한 것은 coverage보다 **안정성**
- 먼저 흔들리지 않는 source graph를 만들고,
- 이후 HTML fallback 군과 analysis 매체를 단계적으로 붙이는 편이 맞다.
