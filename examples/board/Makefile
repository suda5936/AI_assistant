-include .env
export

BACKEND_PY := $(shell [ -x backend/.venv/bin/python ] && echo $(CURDIR)/backend/.venv/bin/python || echo python3)

.PHONY: setup check dev dev-backend dev-frontend e2e e2e-backend e2e-frontend audit coverage openapi

setup:
	$(MAKE) -C backend setup
	cd frontend && npm ci

check:
	$(MAKE) -C backend check
	cd frontend && npm run --silent lint && npm run --silent format:check \
		&& npm run --silent typecheck && npm run --silent test

dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	$(MAKE) -C backend dev

dev-frontend:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort

e2e:
	cd tests/e2e && npm ci && npx playwright test

e2e-backend:
	mkdir -p $(CURDIR)/tests/e2e
	rm -f $(CURDIR)/tests/e2e/e2e.db
	cd backend && DATABASE_URL=sqlite:///$(CURDIR)/tests/e2e/e2e.db $(BACKEND_PY) -m alembic upgrade head
	cd backend && DATABASE_URL=sqlite:///$(CURDIR)/tests/e2e/e2e.db \
		$(BACKEND_PY) -m uvicorn board.main:app --host 127.0.0.1 --port 8001

e2e-frontend:
	cd frontend && API_PROXY_TARGET=http://127.0.0.1:8001 \
		npm run dev -- --host 127.0.0.1 --port 5174 --strictPort

audit:
	$(MAKE) -C backend audit
	cd frontend && npm audit --audit-level=high

coverage:
	$(MAKE) -C backend coverage
	cd frontend && npm run coverage

openapi:
	$(MAKE) -C backend openapi
