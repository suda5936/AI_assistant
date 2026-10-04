PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
TEST_PATHS := ../tests/unit/backend $(wildcard ../tests/acceptance)
LINT_PATHS := . ../tests/unit/backend $(wildcard ../tests/acceptance)

.PHONY: ensure-env setup check lint test coverage audit dev migrate openapi

setup:
	python3.12 -m venv .venv || python3 -m venv .venv
	.venv/bin/python -m pip install -q --upgrade pip
	.venv/bin/python -m pip install -q -e ".[dev]"

ensure-env:
	@$(PY) -c "import board" 2>/dev/null || { echo "환경이 없습니다. 먼저 make setup 을 실행하세요."; exit 1; }

check: lint test

lint: ensure-env
	$(PY) -m ruff check $(LINT_PATHS)
	$(PY) -m ruff format --check $(LINT_PATHS)

test: ensure-env
	$(PY) -m pytest -q $(TEST_PATHS)

coverage:
	$(PY) -m pytest -q --cov=board --cov-fail-under=80 $(TEST_PATHS)

audit:
	.venv/bin/pip-audit --skip-editable

migrate:
	$(PY) -m alembic upgrade head

dev: migrate
	$(PY) -m uvicorn board.main:app --host 127.0.0.1 --port 8000 --reload

openapi:
	$(PY) -m board.openapi_export ../docs/api/openapi.json
