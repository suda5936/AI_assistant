# board — 사내 게시판

회원가입·로그인(HttpOnly 쿠키 세션)과 게시글 작성·조회·수정·삭제를 제공하는 소규모 게시판이다.
FastAPI + SQLite 백엔드, React + TypeScript(Vite) 프론트엔드, Playwright E2E로 구성한다.

## 요구 사항
- Python 3.12, Node 22
- E2E 실행 시 Playwright chromium (`make e2e`가 `tests/e2e`에서 `npm ci` 후 실행)

## 빠른 시작
```bash
make setup      # backend/.venv 생성·설치, frontend npm ci
make check      # 린트·포맷·타입·단위·인수 테스트 (백엔드 + 프론트)
make dev        # 백엔드 8000, 프론트 5173 동시 실행
```
브라우저에서 http://127.0.0.1:5173 을 연다. 개발 서버는 `/api`를 백엔드(8000)로 넘긴다.
`make dev-backend`는 시작 전에 `alembic upgrade head`로 DB(`backend/board.db`)를 만든다.

## 명령
| 명령 | 하는 일 |
|---|---|
| `make setup` | 백엔드 가상환경·의존성, 프론트 의존성 설치 |
| `make check` | 린트·포맷·타입 검사와 테스트 (품질 게이트) |
| `make dev` / `dev-backend` / `dev-frontend` | 개발 서버 |
| `make e2e` | 실제 서버(백엔드 8001, 프론트 5174)를 띄워 Playwright 시나리오 실행 |
| `make audit` | 의존성 취약점 검사 (pip-audit, `npm audit --audit-level=high`) |
| `make coverage` | 커버리지 측정 (백엔드 80% 이상, 프론트 lines·functions 70% 이상) |
| `make openapi` | `docs/api/openapi.json` 갱신 |

## 설정 (환경변수)
`.env.example`을 `.env`로 복사해 값을 채운다. 없어도 기본값으로 동작한다. 비밀값은 필요 없다.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./board.db` | 상대 경로는 `backend/` 기준 |
| `SESSION_COOKIE_SECURE` | `false` | `true`/`1`/`yes`면 쿠키에 Secure 속성. HTTPS 환경에서는 `true` |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | 프론트 개발 서버가 `/api`를 넘길 백엔드 주소 |
| `VITE_API_BASE_URL` | 빈 값(같은 출처) | 프론트가 쓰는 API 기본 URL |

로그인 유지 기간은 7일로 고정이다(환경변수 없음).

## 구조
```
backend/            FastAPI 앱 (src/board: api, services, schemas, models), alembic 마이그레이션
frontend/           React + TypeScript (src: pages, components, api, hooks, utils)
tests/unit/backend/ 백엔드 단위 테스트
tests/acceptance/   QA 인수 테스트 (백엔드 pytest, 프론트 vitest)
tests/e2e/          Playwright E2E (API·브라우저 시나리오, 스크린샷)
docs/               명세(01_spec), 설계(02_design), 마일스톤 설계, 리뷰·QA 기록, API 문서
```

## API 문서
운영 보안을 위해 서버의 `/docs`, `/redoc`, `/openapi.json`은 꺼져 있다(404).
API 명세는 `docs/api/openapi.json`(`make openapi`로 갱신)과 `docs/02_design.md`의 "API 계약" 절을 본다.

엔드포인트: `POST /api/users`(가입), `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`,
`GET·POST /api/posts`, `GET·PUT·DELETE /api/posts/{id}`.
글 목록은 `?page=N`, 페이지당 10개, 최신순. 제목 최대 100자, 내용 최대 5000자(평문).
글 조회는 로그인 없이 가능하고, 작성은 로그인, 수정·삭제는 작성자만 가능하다(남의 글은 403).

## 테스트
- 백엔드 단위·인수: `make -C backend test` (약 3분 걸린다)
- 프론트 단위: `cd frontend && npm run test`
- 프론트 인수 테스트는 `make check`에 포함되지 않는다. 설정 파일마다 따로 실행한다.
  ```bash
  cd tests/acceptance/frontend
  # vitest.config.ts(T-07), vitest.t14.config.ts ~ vitest.t18.config.ts 각각
  npx --prefix ../../../frontend vitest run --config vitest.config.ts
  ```
  (각 설정은 전용 포트의 실제 백엔드를 띄운다. 포트가 겹치지 않도록 하나씩 실행한다.)
- E2E: `make e2e`

## 운영 안내
배포는 이번 범위 밖이다. 운영 환경은 사내 리버스 프록시가 `/api`를 백엔드로 넘기고 `frontend/dist`(`npm run build`)를 정적으로 서빙한다고 가정한다. 다음을 지켜야 한다.
- 프록시는 `/api/` 경로만 백엔드로 넘긴다.
- 프록시의 요청 본문 상한을 64 KiB로 둔다(예: nginx `client_max_body_size 64k`). 백엔드도 같은 상한을 검사하지만 프록시 상한이 1차 방어다.
- 정적 HTML 응답에 보안 헤더를 붙인다: `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`. (API 응답의 헤더는 백엔드가 붙인다)
- HTTPS 종단을 두고 `SESSION_COOKIE_SECURE=true`로 실행한다.
- CORS를 열지 않는다(같은 출처로만 서비스).

## 문제 해결
- 테스트가 수집 단계에서 `ValueError`로 실패하면 셸이나 `.env`의 `SESSION_COOKIE_SECURE` 값을 확인한다(`true/1/yes/false/0/no/빈 값`만 허용).
- 포트 사용 중 오류: 개발 8000·5173, E2E 8001·5174를 쓰는 프로세스를 종료한다.

## 알려진 한계
- 로그인 실패 반복에 대한 잠금(무차별 대입 방어)은 없다(명세 Q9, 이번 범위 제외).
- 모바일 최적화, 마크다운, 회원 탈퇴는 지원하지 않는다.
- react-router 6.x의 open redirect 권고(moderate)가 남아 있다. 이동 경로에 사용자 입력을 쓰지 않아 현재 악용할 수 없고, 해소하려면 v7로 메이저 상향이 필요하다.
