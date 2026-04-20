# Hermes Jarvis 설정 가이드

Hermes Jarvis는 메일과 캘린더 데이터를 짧은 브리핑으로 정리해준다.

이런 용도에 맞다:
- 지금 바로 챙길 일 확인
- 계속 이어지는 일 확인
- 새로 중요해진 일 확인
- 캘린더에 넣을 일정 후보 확인

## 요구사항
- Python 3.11+
- 로컬 Hermes 설치
- 메일 수집이 가능한 환경
- 캘린더 동기화를 원하면 Google Calendar 접근 권한

## 1. clone 및 설치
```bash
git clone https://github.com/JinwangMok/hermes-jarvis.git
cd hermes-jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 2. 로컬 설정 파일 만들기
```bash
cp config/pipeline.yaml config/pipeline.local.yaml
cp config/sender-map.example.md config/sender-map.md
```

## 3. 로컬 설정 수정
`config/pipeline.local.yaml`에서 아래 항목을 먼저 수정:
- `accounts`
- `wiki_root`
- `classification.sender_map_path`
- `classification.self_addresses`
- `classification.work_accounts`
- `hermes.deliver_channel`

sender-aware 분류를 쓰려면:
- `classification.sender_map_path: config/sender-map.md`

## 4. sender map 작성
예시 형식:

```md
- Professor | Ada Lovelace | ada@example.org
- Ph.D. Student | Grace Hopper | grace@example.org / g.hopper@example.org
- M.S. Student | Demo User | you@example.com
```

## 5. 기본 실행 순서
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-mail --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli collect-calendar --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli classify-messages --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-proposals --config config/pipeline.local.yaml
PYTHONPATH=src python3 -m jinwang_jarvis.cli generate-briefing --config config/pipeline.local.yaml
```

## 6. proposal 승인 / 거절
거절:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision reject \
  --reason-code low-value \
  --note "관심없음"
```

승인 후 캘린더 생성:
```bash
PYTHONPATH=src python3 -m jinwang_jarvis.cli record-feedback \
  --config config/pipeline.local.yaml \
  --proposal-id <proposal_id> \
  --decision allow \
  --reason-code other \
  --create-calendar
```

## 7. 자동 실행
```bash
./scripts/install.sh --config config/pipeline.local.yaml --poll-minutes 5
```

## 참고
- 개인 값은 `config/pipeline.local.yaml`에 둘 것
- `config/sender-map.md`는 버전 관리에 올리지 말 것
- 호환성 때문에 모듈 경로는 아직 `jinwang_jarvis`를 사용함
