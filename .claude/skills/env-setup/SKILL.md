---
name: env-setup
description: 프로젝트 환경 구성 규칙. 표준 Makefile 명령(setup, check, run/dev, e2e, audit, coverage), 의존성 고정, .env.example, 파이썬·노드 프로젝트 기본 설정. architect가 실행 방법을 설계할 때, developer가 환경 구성 태스크를 구현할 때, qa·PM이 실행·검증할 때 사용한다.
---

# 환경 구성 규칙

목표: **깨끗한 클론에서 `make setup` 한 번이면 설치되고, 모든 검사와 실행이 `make <명령>` 하나로 된다.** (완료 기준 D3)
훅과 품질 게이트, qa는 이 명령만 사용한다. 프로젝트마다 다른 명령을 외울 필요가 없게 하는 것이 핵심이다.

## 표준 Makefile 명령
| 명령 | 하는 일 | 필수 |
|---|---|---|
| `make setup` | 의존성 설치 (가상환경, npm install 등) | ✅ |
| `make check` | 린트 + 포맷 확인 + 타입 검사 + 단위·인수 테스트. **품질 게이트가 매번 실행**하므로 1~2분 안에 끝나야 한다 | ✅ |
| `make run` / `make dev` | 실행 (CLI는 run, 서비스는 dev: 개발 서버) | ✅ |
| `make e2e` | 서버를 띄워 E2E 시나리오 실행 (서비스만) | 서비스 |
| `make audit` | 의존성 취약점 검사 (pip-audit, npm audit) | 서비스 |
| `make coverage` | 커버리지 측정, 기준 미달 시 실패 | 서비스 |

## 파이썬 프로젝트
- 구조: `src/<패키지>/` + `tests/unit/`, `tests/acceptance/`. 패키지 정보는 `pyproject.toml` 하나에 둔다.
- 가상환경은 프로젝트 안의 `.venv/`. Makefile은 `.venv`가 있으면 그것을, 없으면 시스템 python3를 쓴다.
- **린트 규칙은 회사 공통 `ruff.toml`(하네스 루트)을 프로젝트 루트에 복사해 둔다** (환경 구성 태스크에서). 하네스 밖에 클론해도 같은 규칙으로 검사되어야 하기 때문이다 (D3, lessons L-17).
  - 복사본 첫 줄에 "회사 공통 ruff.toml의 복사본. 회사 규칙이 바뀌면 함께 바꾼다"를 적는다. 규칙을 빼거나 완화하지 않는다. `extend`로 저장소 밖 파일을 참조하지 않는다.
  - `pyproject.toml`에는 `[tool.ruff]`를 두지 않는다 (두면 그 폴더에서 루트 복사본을 가린다).
- pytest 설정은 `pyproject.toml`의 `[tool.pytest.ini_options]`에 둔다 (`pythonpath = ["src"]`, `testpaths = ["tests"]`).
- 의존성은 버전 범위를 명시한다 (예: `fastapi>=0.110,<1`). 개발 도구는 `[project.optional-dependencies] dev`에.

```makefile
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: setup check lint test run
setup:
	python3 -m venv .venv
	.venv/bin/pip install -q -e ".[dev]"

check: lint test

lint:
	ruff check .
	ruff format --check .

test:
	$(PY) -m pytest -q

run:
	$(PY) -m <패키지> $(ARGS)
```

## 노드(프론트엔드) 프로젝트
- `package.json`의 scripts에 `lint`, `typecheck`, `test`, `format`, `dev`, `build`를 둔다. 품질 게이트가 Makefile이 없을 때 이 이름을 찾는다.
- 의존성은 `npm install`로 `package-lock.json`을 만들고 **lock 파일을 커밋한다.** 설치는 `npm ci`.
- 린트·포맷: eslint + prettier. 타입: `tsc --noEmit`. 테스트: vitest.

## 서비스(백엔드 + 프론트엔드)
```
<프로젝트>/
├── backend/      # 파이썬 프로젝트 (자체 pyproject.toml)
├── frontend/     # 노드 프로젝트 (자체 package.json)
├── tests/e2e/    # qa의 E2E 시나리오
├── Makefile      # 아래처럼 하위 프로젝트를 묶는다
├── .env.example
└── README.md
```

```makefile
.PHONY: setup check dev e2e audit coverage
setup:
	$(MAKE) -C backend setup
	cd frontend && npm ci

check:
	$(MAKE) -C backend check
	cd frontend && npm run --silent lint && npm run --silent typecheck && npm run --silent test
```

## 품질 명령의 기준값 (서비스)
- `make coverage`: 백엔드 `pytest --cov=<패키지> --cov-fail-under=80`, 프론트엔드 vitest 커버리지 `lines`·`functions` 70% 이상. 미달이면 실패로 끝나야 한다.
- `make audit`: 백엔드 `pip-audit` (dev 의존성에 추가), 프론트엔드 `npm audit --audit-level=high`. high 이상 취약점이 있으면 실패.
- `make openapi`: 백엔드 앱에서 OpenAPI 문서를 `docs/api/openapi.json`으로 내보낸다 (API 문서, 완료 기준 D7).

## 설정과 비밀값
- 모든 설정은 환경변수로 읽는다. 기본값이 있으면 코드에, 비밀값은 기본값 없이.
- `.env.example`에 **모든 변수**를 설명과 함께 적는다 (실제 비밀값은 쓰지 않는다). 실제 `.env`는 사람이 만들고, 에이전트는 읽거나 쓰지 않는다 (훅이 막는다).
- 테스트는 `.env` 없이 돌아가야 한다. 테스트용 설정은 fixture나 테스트 전용 기본값으로.
- 개발용 DB는 SQLite 파일을 기본으로 한다. PostgreSQL 등이 필요하면 `docker-compose.yml`을 두고 ADR에 이유를 적는다.

## .gitignore (프로젝트마다)
```
.venv/
__pycache__/
.pytest_cache/
.coverage
htmlcov/
node_modules/
dist/
.env
*.db
test-results/
playwright-report/
```

## README에 반드시 들어갈 것
- 요구 사항 (Python 3.12, Node 22 등)
- `cp .env.example .env` → `make setup` → `make run|dev` 순서
- `make check`, `make e2e` 설명
