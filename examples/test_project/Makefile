PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

.PHONY: setup check lint test run
setup:
	python3 -m venv .venv
	.venv/bin/pip install -q -e ".[dev]"

check: lint test

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

test:
	$(PY) -m pytest -q

run:
	PYTHONPATH=src $(PY) -m todo $(ARGS)
