# test_project — 할 일 CLI

터미널에서 할 일을 추가·조회·완료·삭제하고, 다시 실행해도 데이터가 유지되는 CLI. Python 3.11 이상, 표준 라이브러리만 사용한다.

## 실행

```
make setup                          # .venv 생성, 개발 도구(pytest, ruff) 설치
.venv/bin/python -m todo add "우유 사기"
.venv/bin/python -m todo list
.venv/bin/python -m todo done 1
.venv/bin/python -m todo delete 1
```

설치 없이: `PYTHONPATH=src python3 -m todo list`, 또는 `make run ARGS='add "우유 사기"'`.

| 명령 | 동작 | 성공 출력 |
|---|---|---|
| `add "<제목>"` | 추가 (제목 1~100자) | `추가됨: #<번호> <제목>` |
| `list` | 번호 순 목록 | `#<번호> [ ] <제목>` (완료는 `[x]`), 없으면 `할 일이 없습니다` |
| `done <번호>` | 완료 처리 | `완료: #<번호> <제목>` / 이미 완료면 `이미 완료됨: #<번호>` |
| `delete <번호>` | 삭제 (번호는 재사용 안 함) | `삭제됨: #<번호> <제목>` |

오류는 표준 오류에 `오류: ...`로 출력한다. 종료 코드: 0 성공, 1 입력 오류, 2 저장 파일 오류.

저장 파일은 환경변수 `TODO_FILE`, 없으면 현재 폴더의 `todo.json`. 파일이 손상되면 덮어쓰지 않고 코드 2로 끝난다.

## 개발

```
make check    # ruff 린트 + 포맷 확인 + pytest (단위·인수·통합)
make test     # pytest -q 만
```

## 구조

```
src/todo/       cli.py(인자·출력·종료 코드) service.py(규칙) storage.py(JSON 저장) models.py errors.py __main__.py
tests/          unit/(developer) acceptance/(qa) e2e/(qa, 통합 시나리오)
docs/           01_spec.md(명세·AC) 02_design.md(설계) milestones/M1.md reviews/ qa/ history.md
```

## 알려진 한계
- 동시 실행 보호 없음 (명세 제외 사항).
- 제목은 입력 그대로 저장한다 (양끝 공백을 지우지 않음). 공백뿐인 제목은 거부.
- 저장 시 파일 권한이 0600이 된다.
- UTF-8로 인코딩할 수 없는 제목은 저장 실패(코드 2)로 처리한다.
