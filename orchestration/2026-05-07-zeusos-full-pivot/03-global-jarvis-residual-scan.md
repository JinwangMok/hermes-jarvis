# Stage 3 Input — Global Jarvis residual scan

## Scan roots
- `/home/jinwang/workspace`
- `/home/jinwang/wiki`
- `/home/jinwang/.hermes`
- `/home/jinwang/.config/systemd/user`

## Result
진왕님 질문에 대한 답은 **아직 NO**입니다. 로컬 전체 경로/내용에 `jarvis` 잔존이 많습니다.

## Counts
- `/home/jinwang/workspace`: path hits 17,640; content files 5,104.
  - 대부분 현재 repo path `/home/jinwang/workspace/zeus-os` 아래라 repo path/package cutover 전에는 구조적으로 남습니다.
  - 기타: `hermes-safe-restart-bundle/manifests/bundles/jinwang-jarvis.yaml`, update review artifacts.
- `/home/jinwang/wiki`: path hits 1,513; content files 1,860.
  - raw/runs/backups 1,450개: raw/history layer라 rewrite 금지 또는 archive/rename 정책 필요.
  - canonical/generated active pages 59개: Stage 4에서 ZeusOS로 이동/alias/queue 처리 가능.
- `/home/jinwang/.hermes`: path hits 7; content files 5,133.
  - active plugin symlink `~/.hermes/plugins/hermes_jarvis_styled_voice_gateway` 포함.
  - archives/config backups 다수 content hit.
- `/home/jinwang/.config/systemd/user`: path hits 12; content files 11.
  - live legacy `jinwang-jarvis-hermes-health.*` 및 stale cycle/weekly units.

## Classification
1. Stage 3 live/runtime/plugin/systemd/config: `.hermes/plugins`, live systemd, safe-restart bundle manifest, repo-local package path.
2. Stage 4 wiki canonical/generated: `entities/`, `concepts/`, `queries/`, `reports/`, source-registry; raw/runs/backups는 policy상 직접 rewrite 금지/별도 archive strategy.
3. Stage 5 repo package/path/distribution: `/home/jinwang/workspace/zeus-os`, `src/jinwang_jarvis`, `pyproject name`, state/db filenames.
4. Historical artifacts/backups: only after explicit archive policy; do not delete blindly.

## Side-effect note
완전 zero-path는 단순 문자열 sweep이 아니라 repo root rename, package rename, live systemd/plugin symlink migration, wiki canonical move, Hermes config/plugin update, historical archive handling이 모두 끝나야 합니다.
