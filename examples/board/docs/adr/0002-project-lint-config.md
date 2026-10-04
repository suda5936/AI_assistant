# 0002. 린트 설정을 프로젝트 저장소 안에 둔다 (board/ruff.toml)

- 상태: 승인(PM 대행, 2026-10-04, 근거: STATUS.md 결정 기록). 아래 "결과"의 회사 규칙 충돌은 대표 보고 사항
- 날짜: 2026-10-04
- 관련: docs/reviews/T-20-r1.md (Major #1, Minor #2·#3), 완료 기준 D3(깨끗한 클론에서 `make setup` → `make check`), env-setup 스킬 "파이썬 프로젝트", 회사 `ruff.toml`(하네스 루트)

## 맥락
설계(02_design.md)와 env-setup 스킬은 "린트 규칙은 하네스 루트 `ruff.toml`을 물려받고 프로젝트에는 ruff 설정을 두지 않는다"고 정했다. ruff는 검사할 파일의 상위 폴더에서 가장 가까운 설정 파일을 찾으므로, 이 규칙은 저장소가 `/home/user/AI_assistant/workplace/board`에 있을 때만 동작한다. 다른 위치에 클론하면 설정을 찾지 못해 ruff 기본값으로 검사되고, 최종 검수에서 `make check` 린트가 43건 실패했다(D3 위반).
회사 `ruff.toml`의 주석은 `extend = "<이 파일 경로>"`를 권하지만, 이것도 저장소 밖 경로를 참조하므로 같은 문제가 생긴다.

## 결정
1. **위치**: 저장소 루트에 `board/ruff.toml` 하나를 둔다. `backend/pyproject.toml`에는 `[tool.ruff]` 절을 두지 않는다(두면 backend 파일에서는 그쪽이 더 가까워 루트 설정을 가린다).
   - ruff는 `[tool.ruff]`가 없는 `pyproject.toml`을 설정으로 보지 않으므로, `backend/`, `tests/unit/backend/`, `tests/acceptance/`의 모든 파이썬 파일이 실행 위치(cwd)와 관계없이 `board/ruff.toml`을 쓴다. `make lint`, 편집 훅(`check_edit.py`, `--config` 없이 실행), 다른 위치의 클론이 모두 같은 설정을 쓴다.
   - per-file-ignores의 경로가 저장소 루트 기준이 되므로 `"../tests/**"` 같은 우회 패턴이 필요 없다.
2. **내용**: 회사 `ruff.toml`의 규칙을 그대로 복사한다. `extend`로 외부 파일을 참조하지 않는다. 규칙을 하나도 빼거나 완화하지 않는다.
   - 복사하는 항목: `line-length = 100`, `target-version = "py311"`, `[lint] select`(E, W, F, I, N, B, UP, SIM, BLE, T10, T20, S), `[lint.per-file-ignores]`의 `"**/cli.py" = ["T20"]`, `"**/tests/**" = ["S101", "S105", "S106", "S108", "S603", "S607", "T20"]`.
   - 복사하지 않는 항목: `"tests/**"`, `".claude/hooks/**"`, `"scripts/**"`. 하네스 자체 경로 전용이라 board에 해당하는 파일이 없다(T-20 리뷰 r1에서 확인).
   - 파일 첫머리 주석에 "회사 공통 ruff.toml(하네스 루트)의 규칙 복사본. extend 금지. 회사 규칙이 바뀌면 이 파일도 같이 바꾼다"를 적는다.
3. **import 분류(`src`)**: `src`를 지정하지 않는다(기본값). 이 위치에서 기본 `src`는 `board/`, `board/src/`이고 둘 다 `board` 패키지를 담고 있지 않으므로, import 분류가 지금까지 회사 설정 아래에서와 똑같다. 그래서 기존 코드의 import 정렬이 그대로 통과한다. T-20 r1의 `src = ["."]`처럼 분류를 일부러 고정하는 설정은 두지 않는다.
   - `board`를 first-party로 바로잡는 일(`src = ["backend/src"]` + import 재정렬 약 24건)은 **이번에 하지 않는다**. 이유: ① 동작에 영향이 없는 정렬 차이뿐이다. ② 재정렬 대상에 qa 소유인 `tests/acceptance/`가 들어갈 수 있어 developer 혼자 끝낼 수 없고, 중간 상태에서는 품질 게이트(`make check`)가 실패한다. ③ 프로젝트가 최종 검수 단계다. 회사 공통 설정을 쓰는 다른 프로젝트와 분류 방식도 같게 유지된다.

## 대안과 기각 이유
- **`backend/pyproject.toml`의 `[tool.ruff]` (T-20 r1 구현)**: 원래 위치에서는 `tests/` 파일이 여전히 저장소 밖 설정을 쓰고, `"../tests/**"` 우회 패턴과 `src = ["."]` 고정이 필요하다(T-20 r1 Minor #2·#3).
- **`extend = "/home/user/AI_assistant/ruff.toml"`**: 저장소 밖 파일 참조라 D3를 해결하지 못한다.
- **Makefile에서 `ruff --config <경로>`**: 편집 훅은 `--config` 없이 실행하므로 훅과 `make check`의 설정이 달라질 수 있다.
- **first-party로 바로잡고 재정렬**: 위 결정 3의 이유로 지금은 하지 않는다.

## 결과
- 새 도구·라이브러리·규칙이 없다(ruff와 규칙 집합은 그대로). 표준 스택(`/docs/adr/0001-standard-stack.md`) 범위 안이다.
- 회사 규칙이 바뀌어도 자동으로 따라가지 않는다. 복사본을 함께 고쳐야 한다(파일 주석으로 안내).
- **회사 규칙과의 충돌(대표 보고 사항)**: env-setup 스킬의 "`pyproject.toml`에 `[tool.ruff]`를 따로 만들지 않는다(하네스 루트 `ruff.toml` 상속)"와 회사 `ruff.toml` 주석의 `extend` 권고는 같은 스킬의 목표(D3 깨끗한 클론)와 충돌한다. 이 결정은 그 문장의 예외다. 다른 프로젝트에도 같은 문제가 생기므로 스킬·회사 설정 문구를 고칠지는 대표가 정한다(하네스 수정은 에이전트 권한 밖).
