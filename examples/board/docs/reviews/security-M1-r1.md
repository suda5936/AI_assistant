판정: 통과

# M1 보안 리뷰 1회차

- 범위: M1 엔드포인트 `POST /api/users`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`와 프론트엔드(`frontend/src`)
- 기준: docs/02_design.md, docs/milestones/M1.md, docs/adr/0001-auth-storage.md, docs/01_spec.md (Q9 확정 한계)
- 결과: Critical 0, Major 0, Minor 3

## 실행 결과
- 테스트: 백엔드 `pytest -q ../tests/unit/backend ../tests/acceptance` 313 passed. 프론트 `vitest run` 56 passed.
- `make audit`
  - 첫 실행 때 pip-audit가 PyPI 503(`license-expression` 조회)으로 `ServiceError`가 나서 실패했다. 일시적인 네트워크 오류였다. 다시 실행하니 `No known vulnerabilities found`로 통과했다.
  - `npm audit --audit-level=high`: 첫 실행은 레지스트리 400(quick 엔드포인트)으로 실패했고, 다시 실행하니 bulk 엔드포인트로 성공했다. **high 0, critical 0, moderate 5**로 통과했다. 각 항목은 아래 S12에 적었다.
- 정적 검사
  - `grep -rn "execute(\|text(" backend/src backend/migrations`: `db.py:19` `PRAGMA foreign_keys=ON` 고정 문자열뿐이다. `openapi_export.py:18`은 `Path.write_text`이므로 SQL이 아니다.
  - 프론트 `dangerouslySetInnerHTML|innerHTML|eval|localStorage|document.cookie`: 운영 코드에서 0건이다. 테스트 파일(`main.test.tsx:10`, `AuthProvider.test.tsx`)에만 있다.
  - `git grep` 비밀값 패턴: 실제 비밀값은 없다. `tests/acceptance/test_t05_auth.py:113`은 테스트용 폼 본문 문자열이다.
- 재현 확인: 앱을 TestClient와 임시 SQLite DB로 띄워 아래 항목을 요청으로 확인했다. 임시 파일은 끝난 뒤 삭제했다.

## 항목별 확인 (근거)
| # | 결과 | 근거 |
|---|---|---|
| S1 | 이상 없음 | `services/passwords.py:19-32`에서 scrypt(n=16384, r=8, p=1)와 16바이트 솔트를 쓴다. 비교는 `hmac.compare_digest`(:47)이다. `test_ac5_hash_stored_in_db_is_not_plaintext` 등이 이를 검증한다 |
| S2 | 이상 없음 | 토큰은 `secrets.token_urlsafe(32)`(`services/sessions.py:20`, 43자)이고 DB에는 SHA-256만 저장한다. 쿠키는 `HttpOnly; SameSite=lax; Path=/; Max-Age=604800`(`api/auth.py:38-46`)이다. 로그아웃하면 행을 삭제한다(`sessions.py:46-51`). 재현: 로그아웃한 뒤 이전 토큰으로 `/me`를 요청하면 401이다. 로그인 전에 공격자가 심어 둔 쿠키(`board_session=attacker-chosen`)가 있어도 로그인하면 새 토큰이 발급되므로 세션 고정이 불가능하다 |
| S3 | 이상 없음 | 인증이 필요한 엔드포인트는 `/me` 하나이고 `Depends(get_current_user)`(`api/auth.py:70`)가 붙어 있다. `test_me_without_cookie_is_401`, `test_me_with_bad_cookie_is_401`, `test_me_with_expired_session_is_401`가 있다 |
| S4 | 해당 없음 | M1에는 소유 리소스가 없다. `/me`는 세션의 사용자만 돌려준다 |
| S5 | 이상 없음 (Minor 1 참고) | Pydantic 스키마(`schemas/user.py`)는 타입만 보고, 길이·형식은 서비스가 검증한다(`services/validation.py`). scrypt를 치르기 전에 길이를 검사하므로 5MB 비밀번호 로그인은 401(48 ms), 가입은 422(78 ms)로 끝나 해시 DoS가 없다. 72자 4바이트 문자(288바이트)는 정상 처리된다. 페이지 크기 상한은 M2 대상이다 |
| S6 | 이상 없음 | ORM `select()`만 쓴다. 문자열로 조합한 SQL이 없다 |
| S7 | 이상 없음 | 사용자 입력과 서버 메시지는 JSX 텍스트(`LoginPage.tsx:41`, `SignupPage.tsx:51,73,95`)로만 렌더링한다. `react/no-danger` 린트 규칙도 켜져 있다 |
| S8 | 이상 없음 | 아래 "CSRF 구성 평가" |
| S9 | 이상 없음 | `.env.example`에 4개 변수(`DATABASE_URL`, `SESSION_COOKIE_SECURE`, `API_PROXY_TARGET`, `VITE_API_BASE_URL`)가 설명과 함께 있고 비밀값은 없다. `.env`, `*.db`는 `.gitignore`에 들어 있다. 설계상 서명 키가 없다 |
| S10 | 이상 없음 | 500 처리기(`errors.py:130-135`)는 고정 메시지만 낸다(`test_unexpected_exception_hides_internal_info`). 422 `details`는 입력값을 되돌려 보내지 않는다. 재현: `{"username":["<script>"]}`를 보내면 field와 고정 메시지만 온다. 로그인 실패는 모든 경우 같은 401 메시지다. 재현 시 응답 시간은 있는 아이디+틀린 비밀번호 65 ms, 없는 아이디 58 ms, 서로게이트 비밀번호는 있는 아이디 6.0 ms, 없는 아이디 5.7 ms로 존재 여부와 무관했다 |
| S11 | 이상 없음 | 로그는 `logger.exception("처리되지 않은 예외")`(`errors.py:131`) 하나다. 요청 본문, 쿠키, 토큰을 기록하지 않는다 |
| S12 | 통과 (moderate 5) | `@vitest/mocker`·`vitest`·`@vitest/coverage-v8`(GHSA-82fw-gwwq-j7x9)은 개발·테스트 도구라 운영 번들에 들어가지 않는다. `react-router`·`react-router-dom` 6.30.6(GHSA-wrjc-x8rr-h8h6 백슬래시 open redirect, GHSA-337j-9hxr-rhxg SSR 전용)은 이 앱이 SSR을 쓰지 않는다. 또 `navigate`의 대상은 모두 고정 문자열(`LoginPage.tsx:30`, `Header.tsx:16`, `SignupPage.tsx:41`)이라 악용 경로가 없다. 설계 결정("react-router-dom 6 유지")과 일치한다. Minor 3 참고 |
| S13 | 한계 (Q9) | 명세 Q9에서 제외가 확정됐다. 아래 "알려진 한계" |

## CSRF 구성 평가 (SameSite=Lax + JSON 전용 415)
결론: M1 구성으로 교차 사이트 요청 위조가 막힌다. 재현으로 확인한 사항은 아래와 같다.
- **Content-Type 검사**(`api/middleware.py:22-28`): 라우팅보다 앞에서 동작한다. `text/plain`, `application/x-www-form-urlencoded`, `multipart/form-data`는 HTML 폼이나 단순 요청으로 보낼 수 있는 유형인데 모두 415다. Content-Type이 없어도 415다. `application/json-patch+json`, `application/jsonx`, `text/plain; application/json`처럼 비슷한 값도 모두 415다. 대소문자 변형과 `; charset`은 허용된다. 이것은 문제가 아니다. 이런 값은 브라우저가 단순 요청으로 보낼 수 없어 사전 요청(preflight)이 필요하기 때문이다.
- **경로 우회 시도**: `/api//auth/logout`, `/%61pi/auth/logout`, `/api/auth/logout/`, `/api/auth/./logout`에 `text/plain`으로 보내면 모두 415다. `/API/...`는 404다(라우트에 닿지 않음). 모든 라우트가 `/api/` 아래에 있으므로 접두사 검사를 빠져나가는 경로가 없다.
- **사전 요청 차단**: CORS 미들웨어가 없다. `OPTIONS`에 `Origin: https://evil.example`를 붙여 보내면 405가 오고 `Access-Control-Allow-*` 헤더가 없다. 따라서 다른 출처의 `fetch`가 `application/json`으로 요청하면 브라우저가 막는다. 교차 출처 POST 응답에도 `Access-Control-Allow-Origin`이 없다.
- **GET에 부작용 없음**: `GET /api/auth/logout`, `GET /api/users`는 405다. 상태를 바꾸는 GET이 없으므로 Lax 쿠키가 최상위 이동에 실려 가도 악용할 수 없다.
- **로그인 CSRF와 강제 로그아웃**도 같은 이유로 막힌다.
- 남는 전제: 이 방어는 "CORS를 열지 않는다"는 전제에 기대고 있다. 같은 사이트의 다른 출처(형제 서브도메인)는 SameSite=Lax 쿠키를 보낼 수 있지만, 다른 출처이므로 JSON 요청에 사전 요청이 필요해 역시 막힌다. 남는 위험은 같은 출처에서 실행되는 XSS뿐이고, 이는 S7로 관리한다. Origin 헤더 검사는 없다(심층 방어로는 선택 사항). M2에서도 아래 Minor 3의 조건을 지키면 유효하다.

## 발견 사항
| # | 등급 | 위치 | 문제와 재현 | 수정 지시 | 담당 |
|---|---|---|---|---|---|
| 1 | Minor | `backend/src/board/main.py` (앱 전체), 02_design.md "배포" | 요청 본문 크기에 상한이 없다. 재현: 인증 없이 `POST /api/users`에 20MB JSON(`{"username":"zz","password":"p","pad":"x"*20000000}`)을 보내면 서버가 본문 전체를 메모리에 올려 파싱한 뒤 422를 돌려준다(0.14 s). 동시에 여러 번 보내면 메모리 압박을 줄 수 있다. 운영에서는 리버스 프록시를 가정하지만 설계와 README에 상한이 적혀 있지 않다 | 설계의 "배포" 가정에 리버스 프록시의 본문 상한(예: 64KB, M2 내용 5000자를 감안)을 명시하고 README에 반영한다. 또는 백엔드에서 `Content-Length` 상한 미들웨어(초과 시 413)를 둘지 결정한다 | architect |
| 2 | Minor | 02_design.md "배포", `backend/src/board/main.py:16` | 보안 응답 헤더(`Content-Security-Policy`/`frame-ancestors`, `X-Content-Type-Options`)가 없다. 로그인 화면을 iframe에 넣는 클릭재킹을 막지 못한다. FastAPI 기본 `/docs`, `/openapi.json`은 200으로 공개된다. 이들은 `/api` 밖이라 Vite 프록시와 "운영 프록시는 `/api`만 넘김" 가정에서는 노출되지 않지만, 이 가정은 문서에만 있다 | 운영 리버스 프록시 가정에 보안 헤더 설정과 `/docs`·`/openapi.json` 비노출을 명시한다. 또는 `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`처럼 운영에서 끌지 결정한다. `make openapi`는 `app.openapi()`를 직접 부르므로 영향이 없는지 확인한다 | architect |
| 3 | Minor | M2 설계 예정, `frontend/package.json`(react-router-dom 6.30.6) | `react-router` moderate 권고(GHSA-wrjc-x8rr-h8h6)는 지금은 악용 경로가 없다. 그러나 M2에서 `?next=` 같은 사용자 제어 값을 `navigate`/`<Link to>`에 넘기면 백슬래시 open redirect가 실제 위험이 된다. 또 CSRF 방어가 "CORS 없음"에 기대므로 CORS를 추가하면 방어가 무너진다 | M2 설계에 다음을 적는다. (a) 이동 대상은 앱 내부 고정 경로나 서버가 준 숫자 ID로만 만든다. (b) `allow_origins=["*"]`+credentials를 포함해 CORS를 열지 않는다. (c) 삭제(DELETE)도 `Content-Type: application/json`을 보낸다(이미 계약에 있음, 유지) | architect |

## 알려진 한계 (반려 사유 아님)
| 한계 | 근거 | 영향 |
|---|---|---|
| 로그인 무차별 대입 제한 없음 | 명세 Q9 확정, ADR 0001 "결과" | 같은 아이디에 비밀번호를 계속 대입할 수 있다. 8자 이상 정책과 scrypt 비용(요청당 약 60 ms)이 속도를 늦출 뿐이다 |
| 인증 없는 scrypt 비용 | Q9와 같은 원인 | 로그인·가입 1건마다 scrypt(약 16MB 메모리, 수십 ms)를 치른다. 요청 제한이 없으므로 동시 요청을 대량으로 보내면 CPU와 메모리를 소모시킬 수 있다(동기 엔드포인트라 스레드풀 크기만큼 병렬) |
| 가입으로 아이디 존재 확인 가능 | AC-2(409 `username_taken`) | 로그인은 존재 여부를 숨기지만 가입 API로는 확인할 수 있다. 명세가 요구하는 동작이다 |
| `SESSION_COOKIE_SECURE` 기본값 false | 02_design.md "설정", Q11 | HTTPS 운영에서 true로 설정하지 않으면 쿠키가 평문 HTTP로도 전송된다. README 운영 안내에 반드시 적어야 한다(PM 최종 검수) |
| 세션 정리·동시 세션 제한 없음 | ADR 0001 "결과" | 만료된 세션 행은 조회될 때만 지워진다. 다시 로그인해도 기존 세션이 남는다. 다른 세션을 강제로 끊는 기능도 없다 |
| CSRF 방어가 브라우저 사전 요청에 의존 | 위 "CSRF 구성 평가" | CORS를 열거나 같은 출처에 XSS가 생기면 무력화된다 |
