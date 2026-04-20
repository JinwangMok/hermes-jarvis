# 퍼블릭 설정 가이드 (한국어)

이 문서는 `jinwang-jarvis`를 누구나 Hermes와 함께 재사용할 수 있게 설정하는 방법을 설명해.

## 1. 이런 용도에 맞음
다음을 정리하고 싶을 때 적합해:
- 최근 중요해진 메일/일
- 예전부터 계속 중요한 흐름
- 새로 중요해진 흐름
- 캘린더에 올릴 만한 일정 후보

## 2. 최소 요구사항
- Python 3.11+
- 로컬 Hermes 설치
- 메일 수집용 CLI 환경(이 레포는 Himalaya 기반)
- 캘린더 수집/생성을 원하면 Google Calendar 접근 권한

## 3. 설정 파일 전략
추적되는 공개용 예시:
- `config/pipeline.yaml`

개인 실사용 권장 파일:
- `config/pipeline.local.yaml`

설치 스크립트는 `config/pipeline.local.yaml`이 있으면 그 파일을 자동 우선 사용해.

## 4. 꼭 바꿔야 하는 항목
`config/pipeline.local.yaml`에서 주로 수정할 것:
- `accounts`
- `classification.sender_map_path`
- `classification.self_addresses`
- `classification.work_accounts`
- `hermes.deliver_channel`
- `wiki_root`

## 5. sender map 형식
아래처럼 markdown bullet 형식이면 돼:

```md
- Professor | Ada Lovelace | ada@example.org
- Ph.D. Student | Grace Hopper | grace@example.org / g.hopper@example.org
- M.S. Student | Demo User | you@example.com
```

## 6. 기본 실행 순서
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
```

## 7. 승인 루프
일정 후보를 보고 decision을 기록할 때:

거절:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision reject \
  --reason-code low-value \
  --note "관심없음"
```

승인 + 캘린더 생성:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other \
  --create-calendar
```

## 8. 자동 폴링 설치
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

## 9. Hermes와 함께 쓸 때 팁
- 개인 경로/개인 채널/개인 이메일은 추적 파일에 넣지 말 것
- 운영 상태는 `state/`, `data/`에 두고
- 위키는 장기 synthesis 메모 계층으로 쓰는 게 좋음
