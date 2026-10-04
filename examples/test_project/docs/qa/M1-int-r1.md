판정: 반려

# M1 통합 검증 1회차

## 실행 결과
- 회귀: `python3 -m pytest -q` → 287개 통과, 0개 실패 (단위·인수 286 + 신규 통합 1). AC-1~AC-10 인수 테스트 전부 통과.
- 린트: 이 환경에 ruff 모듈이 없어 실행하지 못함 (훅이 신규 파일 검사 통과).
- 실제 프로세스 실행: `python -m todo`를 임시 폴더에서 subprocess로 실행하고 종료 코드·stdout·stderr를 개별 확인. 시나리오 1~8은 기대와 정확히 일치. **시나리오 9에서 불일치.**
- 서버/브라우저 E2E는 CLI라 해당 없음.
- 참고: 회사 ruff 규칙(S603) 때문에 `tests/e2e/`에 subprocess 테스트를 둘 수 없어, `tests/e2e/test_m1_integration.py`는 runpy 방식(설계 지침)으로 작성했다. 이 방식은 아래 결함 #1을 잡지 못한다(pytest 환경에서는 로깅 핸들러 동작이 달라 통과함).

## 발견 사항
| # | 등급 | 위치 | 문제 | 수정 지시 | 담당 |
|---|---|---|---|---|---|
| 1 | Major | src/todo/storage.py:42 (같은 방식으로 :64, :76, :88) | 로거 설정이 없어 `logger.warning`이 Python 기본 핸들러(lastResort)를 통해 실제 프로세스의 표준 오류로 새어 나온다. 시나리오 9 (`{깨짐` 파일에 `list`/`add "x"`)의 stderr가 `저장 파일 읽기 실패: todo.json (Expecting property name enclosed in double quotes: line 1 column 2 (char 1))\n오류: 저장 파일을 읽을 수 없습니다: todo.json\n` 두 줄이다. 시나리오와 AC-10은 stderr가 `오류: 저장 파일을 읽을 수 없습니다: <경로>`임을 요구하고, 설계도 storage는 "출력하지 않는다"고 한다. 종료 코드 2와 파일 바이트 불변은 정상. 쓰기 실패(서로게이트 제목 등)도 같은 경로로 추가 줄이 나올 것으로 보인다(미실행). | 정상 실행 시 사용자에게 로그 줄이 보이지 않게 한다(예: 로그 수준을 낮추거나 패키지 로거에 NullHandler 추가 등 설계에 맞는 방법). 수정 후 실제 프로세스로 stderr가 오류 한 줄뿐인지 확인할 수 있는 검사를 단위 테스트에 추가(예: handler 없이 stderr 캡처). 설계 선택이 필요하면 architect와 협의 | developer |

## 통합 검증 시나리오 확인
| 시나리오 | 결과 |
|---|---|
| 1 list 빈 상태, 파일 미생성 | 통과 |
| 2 add 2건 (#1, #2) | 통과 |
| 3 done / 재실행 | 통과 |
| 4 list 형식 | 통과 |
| 5 delete 2 후 add → #3 | 통과 |
| 6 없는 번호·abc, 코드 1 | 통과 |
| 7 빈/공백/101자 거부 및 파일 불변, 100자 성공 | 통과 |
| 8 TODO_FILE 별도 경로, todo.json 불변 | 통과 |
| 9 손상 파일 | 코드 2·파일 불변은 통과, **stderr에 추가 로그 줄 (결함 #1)** |

## AC 확인
| AC | 테스트 | 결과 |
|---|---|---|
| AC-1~AC-9 | tests/acceptance/ 전체, tests/e2e/test_m1_integration.py, 실제 프로세스 실행 | 통과 |
| AC-10 | tests/acceptance/test_t02_storage.py, test_t04_cli.py (통과) / 실제 프로세스 stderr | 부분 실패: 종료 코드·불변은 통과, stderr 정확도는 결함 #1 (명세에서 "stderr가 오직 오류 한 줄"인지는 엄격히 명시되지 않았으나 시나리오 9와 설계가 요구) |
