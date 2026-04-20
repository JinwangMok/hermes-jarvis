# Hermes Jarvis 제품화 가이드

이 문서는 **Hermes를 새로 설치한 사람도** 메일/캘린더/위키/디스코드 기반의 개인 비서형 Jarvis를 구축할 수 있도록 정리한 운영 가이드다.

목표는 다음과 같다.
- 새 메일이 들어오면 로컬 DB와 위키 기반 데이터소스에 반영
- 기존 맥락(thread / participant / project / memory)을 유지하며 갱신
- 아침 8시(한국시간) 디스코드로 모닝 브리핑 보고
- 향후 정보 소스 감시(watch sources)와 TODO/일정 추천까지 확장

## 1. 구성 요소

핵심 저장소는 모두 **로컬 파일**이다.
- SQLite DB: `state/personal_intel.db`
- 체크포인트: `state/checkpoints.json`
- 위키 노트: `wiki/queries/...`
- 인텔리전스 아티팩트: `data/intelligence/...`

즉 재부팅 후에도 파일시스템이 유지되면 메모리/이력/분석은 유지된다.

## 2. 필수 준비물

- Python 3.11+
- Hermes 로컬 설치
- 메일 접근 수단
  - 권장: Gmail + OAuth + Himalaya CLI
- (선택) Google Calendar 접근
- (권장) Obsidian/Markdown 위키 경로
- (선택) Discord 연결된 Hermes

## 3. Gmail / Himalaya 준비

Jarvis는 자체적으로 Gmail 인증을 만들지 않는다. **메일 수집이 가능한 Himalaya 계정 환경**이 먼저 준비되어야 한다.

최소 요구:
- Gmail OAuth client 준비
- Himalaya account 설정 완료
- 메일함 조회 성공
- `All Mail` / `전체보관함` 접근 가능 확인

확인 예시:
```bash
himalaya account list
himalaya folder list -a personal
himalaya envelope list -a personal --folder INBOX --page 1 --page-size 5 --output json
```

권장 확인 포인트:
- `INBOX`
- `보낸편지함`
- `[Gmail]/전체보관함` 또는 archive-like folder

## 4. 기본 설정

```bash
cp config/pipeline.yaml config/pipeline.local.yaml
cp config/sender-map.example.md config/sender-map.md
```

`config/pipeline.local.yaml`에서 최소 수정:
- `accounts`
- `wiki_root`
- `classification.sender_map_path`
- `classification.self_addresses`
- `classification.work_accounts`
- `hermes.deliver_channel`

권장:
- `wiki_root`는 Obsidian vault 내부 경로
- `hermes.deliver_channel`은 디스코드 보고 채널/스레드에 맞춤 설정

## 5. 첫 실행 순서

```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-knowledge-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-daily-intelligence --config config/pipeline.local.yaml
```

이 단계까지 끝나면:
- operational lane: `INBOX + sent`
- knowledge lane: `All Mail`
- wiki priority/intelligence notes
- daily intelligence artifact

가 생성된다.

## 6. 운영 lane / knowledge lane 개념

### operational lane
목적:
- 지금 답할 메일
- 곧 처리할 액션
- 일정 후보

데이터 소스:
- `INBOX`
- `sent`

### knowledge lane
목적:
- 오래 이어지는 흐름
- 정보성 메일
- 교육/프로젝트/특허/제안서/기술 트렌드
- 장기 기억 및 위키 note

데이터 소스:
- `All Mail` / `전체보관함`

이 두 lane을 분리해야 **운영 정확도**와 **장기 recall**을 동시에 잡을 수 있다.

## 7. 재부팅 후 자동 재개

권장 설치:
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

또는:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli install-systemd --config config/pipeline.local.yaml --poll-minutes 5
```

### 중요: linger 설정
로그인 없이도 user systemd timer가 재부팅 후 계속 돌게 하려면 보통 아래가 필요하다.

```bash
sudo loginctl enable-linger $USER
```

확인:
```bash
loginctl show-user $USER | grep Linger
systemctl --user status
systemctl --user list-timers
```

문제 없으면:
- 재부팅 후에도 polling loop 재개
- mail/calendar/classification/intelligence 갱신 지속

## 8. 아침 8시 디스코드 모닝 브리핑

권장 구조는 두 층이다.

### 층 1: polling loop (5분)
역할:
- 새 메일 수집
- 캘린더 수집
- 분류/knowledge lane 업데이트
- participant cache/backfill 점진 보강

### 층 2: morning digest (매일 08:00 KST)
역할:
- 어제/오늘 새 메일 반영 결과 요약
- daily/weekly 정보성 메일 포함
- 기존 중요 흐름 변화 요약
- TODO / 일정 추천 초안 생성
- 디스코드 채널 보고

즉, **수집은 자주 / 보고는 정시** 구조가 좋다.

## 9. morning briefing에 포함할 권장 항목

- 지금 답/확인해야 하는 메일
- 최근 중요해진 일
- 계속 중요했던 일
- 교수/상사/협업자 action chain 변화
- daily/weekly 정보성 메일 핵심 포인트
- 향후 일정 후보
- 추천 TODO

## 10. participant cache / thread graph

장기적으로 정확도를 올리려면 header cache가 중요하다.

수집 필드:
- `Message-ID`
- `In-Reply-To`
- `References`
- `To/Cc/Reply-To/Delivered-To`

이걸 기반으로:
- thread relation
- participant context
- work-item inference
- advisor action note
- project note

정확도가 올라간다.

## 11. watch source 확장 방향

향후 “진짜 Jarvis”로 가려면 메일 외에도 아래를 추가할 수 있다.
- RSS / 블로그
- 학회 CFP
- 스타트업/지원사업 공고
- 기술 벤더 뉴스레터
- 내부 프로젝트 대시보드

권장 원칙:
- 원천 데이터는 DB/파일
- 위키는 synthesis / memory
- daily digest에서 메일과 watch source를 함께 요약

## 12. 퍼블릭 레포 목적

퍼블릭 레포의 목표는 단순 샘플이 아니다.

목표:
1. 새 사용자도 Gmail/OAuth/Himalaya/위키/Discord를 연결할 수 있게 하기
2. local-first 개인 비서 파이프라인을 재현 가능하게 하기
3. 메일 → 기억 → 브리핑 → 추천 루프를 제품처럼 운영 가능하게 하기

즉 README만 보는 사람이 아니라, **Hermes를 새로 설치한 사용자**가 그대로 따라 하면 개인용 Jarvis를 만들 수 있어야 한다.

## 13. 체크리스트

### 최소 동작
- [ ] `collect-mail` 성공
- [ ] `collect-calendar` 성공(선택)
- [ ] `classify-messages` 성공
- [ ] `collect-knowledge-mail` 성공
- [ ] `generate-daily-intelligence` 성공
- [ ] 위키 note 생성 확인

### 자동 운영
- [ ] systemd user timer 설치
- [ ] `loginctl enable-linger $USER`
- [ ] 재부팅 후 timer 재개 확인

### 모닝 브리핑
- [ ] 매일 08:00 KST 스케줄 등록
- [ ] Discord 전달 경로 확인
- [ ] 어제/오늘 새 메일 반영 확인
- [ ] 정보성 메일 요약 포함 확인

## 14. 추천 운영 원칙

- 메일은 polling 기반으로 처리
- 위키는 source of truth가 아니라 memory/synthesis 레이어
- 운영 lane과 knowledge lane을 분리
- participant cache는 staged backfill로 점진 보강
- 아침 브리핑은 “정보 과잉”이 아니라 “행동 우선”으로 유지
