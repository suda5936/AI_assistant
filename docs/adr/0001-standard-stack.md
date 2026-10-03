# 0001. 회사 표준 서비스 스택

- 상태: 채택
- 날짜: 2026-10-03

## 맥락
하네스는 명세만 받으면 백엔드, 프론트엔드, DB가 있는 서비스를 끝까지 만들어야 한다. 스택이 프로젝트마다 달라지면 코딩 규칙, 훅, E2E 절차를 매번 새로 만들어야 하므로 **기본 스택 하나를 정하고 그 스택에 하네스를 맞춘다.** 다른 스택이 꼭 필요하면 프로젝트의 `docs/adr/`에 이유를 적고 사용자 승인을 받는다.

## 결정
| 영역 | 선택 | 비고 |
|---|---|---|
| 백엔드 언어 | Python 3.12 | 회사 공통 `ruff.toml`로 린트 |
| 웹 프레임워크 | FastAPI | Pydantic v2로 요청·응답 검증, OpenAPI 문서 자동 생성 |
| DB 접근 | SQLAlchemy 2.x (ORM) | 문자열 조합 SQL 금지 |
| 마이그레이션 | Alembic | 스키마 변경마다 마이그레이션 파일 |
| DB | SQLite (개발·테스트) | 운영 DB가 필요하면 PostgreSQL + docker compose (프로젝트 ADR) |
| 인증 | 서버 세션 + HttpOnly 쿠키 | 비밀번호 해시: 표준 라이브러리 `hashlib.scrypt` 또는 argon2 |
| 백엔드 테스트 | pytest, FastAPI TestClient(httpx), pytest-cov | |
| 프론트엔드 | React + TypeScript (strict) + Vite | 라우팅: React Router |
| 프론트 품질 | eslint + prettier + `tsc --noEmit` | 훅과 품질 게이트가 실행 |
| 프론트 테스트 | vitest + Testing Library | |
| E2E | Playwright (`@playwright/test`) | 이 환경의 브라우저에 맞춰 1.56.1 고정. 로컬에서는 `npx playwright install chromium` |
| 실행 표준 | Makefile (`setup`, `check`, `dev`, `e2e`, `audit`, `coverage`) | env-setup 스킬 |

## 대안과 기각 이유
- **Django**: 기능이 많지만 작은 서비스에는 무겁고, API 계약 우선 설계(OpenAPI)는 FastAPI가 더 자연스럽다.
- **Next.js 풀스택**: 하나의 언어로 끝나지만, 이미 만든 파이썬 규칙·훅을 버려야 하고 백엔드와 프론트엔드의 역할 분리가 흐려진다.
- **JWT를 localStorage에 저장**: 구현은 쉽지만 XSS에 취약하다. HttpOnly 쿠키 세션을 기본으로 한다.

## 결과
- 하네스의 스킬(coding-standards, frontend-standards, api-design, env-setup, e2e-testing)과 훅은 이 스택을 기준으로 한다.
- 다른 스택을 쓰는 프로젝트는 자동 검사 일부가 적용되지 않을 수 있다 (훅은 프로젝트에 설치된 도구만 실행한다).
