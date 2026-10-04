판정: 통과

# M1 통합 검증 2회차 (T-05 QA 겸함)

## 실행 결과
- 회귀: `python3 -m pytest -q` → 291개 통과, 0개 실패 (1회차 287개에서 T-05가 추가한 단위 테스트 4개 증가). AC-1~AC-10 인수 테스트와 tests/e2e/test_m1_integration.py 포함.
- 린트: 이 환경에 ruff 모듈이 없어 실행하지 못함 (1회차와 동일, 훅/품질 게이트에 위임).
- 실제 프로세스 실행: 임시 폴더에서 `python -m todo`를 subprocess로 실행(일회성 스크립트, 저장소에 파일을 남기지 않음)하고 코드·stdout·stderr를 개별 확인했다.
  - 시나리오 1~9 전부 기대와 일치. 오류 케이스의 stderr는 모두 오류 한 줄(개행 1개)이다.
  - 시나리오 9: `{깨짐` 파일에 `list`, `add "x"` → stderr는 `오류: 저장 파일을 읽을 수 없습니다: todo.json` 한 줄, 코드 2, 파일 바이트 불변. 1회차 결함 #1 해소.
  - 쓰기 실패 (없는 폴더 경로 `TODO_FILE=<임시>/nodir/x.json`에서 `add`) → stderr `오류: 저장 파일을 쓸 수 없습니다: <경로>` 한 줄, 코드 2, stdout 비어 있음, 폴더가 만들어지지 않음.
  - 쓰기 실패 (서로게이트 제목 `a\udcffb`를 argv로 전달) → stderr `오류: 저장 파일을 쓸 수 없습니다: todo.json` 한 줄, 코드 2, stdout 비어 있음, `todo.json` 미생성.
  - 추가 확인: 저장 경로가 디렉터리일 때 `add`/`list` → 읽기 오류 한 줄, 코드 2.
- 서버/브라우저 E2E는 CLI라 해당 없음.

## 발견 사항
| # | 등급 | 위치 | 문제 | 수정 지시 | 담당 |
|---|---|---|---|---|---|
| - | - | - | Critical/Major 없음 | - | - |

참고(비차단): 이월 Minor는 STATUS.md 기재대로 유지. 서로게이트 `\ud800`을 argv로 직접 넘기는 것은 OS 수준에서 불가능해 `\udcff`(surrogateescape)만 실제 프로세스로 확인했다.

## 통합 검증 시나리오 확인
| 시나리오 | 결과 |
|---|---|
| 1~8 | 통과 (1회차와 동일, stderr 추가 줄 없음) |
| 9 손상 파일 | 통과 (stderr 한 줄, 코드 2, 바이트 불변) |
| 쓰기 실패 2종 | 통과 (stderr 한 줄, 코드 2) |

## AC 확인
| AC | 테스트 | 결과 |
|---|---|---|
| AC-1 ~ AC-9 | tests/acceptance/test_t01~t04, tests/e2e/test_m1_integration.py, 실제 프로세스 | 통과 |
| AC-10 | tests/acceptance/test_t02_storage.py, test_t04_cli.py, 실제 프로세스 시나리오 9 | 통과 |
| T-05 (stderr 로그 누수 수정) | tests/unit/test_stderr_clean.py, 실제 프로세스 | 통과 |
