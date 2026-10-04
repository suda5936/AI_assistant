판정: 통과

# M2 보안 리뷰 1회차 (게시글 CRUD)

- 범위: `GET/POST /api/posts`, `GET/PUT/DELETE /api/posts/{post_id}`, 요청 보호 미들웨어(T-13), 프론트 게시글 화면(T-14~T-18)
- 기준: security-checklist S1~S13, 02_design.md "API 계약", M2.md "보안 조건"

## 실행 결과
- `make audit` (종료 코드 0)
  - pip-audit: `No known vulnerabilities found`
  - npm audit --audit-level=high: high 이상 0건. moderate 5건(react-router 6.30.6, vitest/@vitest/mocker/@vitest/coverage-v8 3.2.7) → 발견 사항 #1, #2
- 단위 테스트: `pytest -q tests/unit/backend/test_api_posts.py test_posts_service.py test_security_middleware.py` → 119 passed
- 공격 재현(TestClient + 공유 인메모리 SQLite, alice 글을 bobby·비로그인으로 공격): 아래 "이월 항목 확인"과 "IDOR 확인"의 결과가 이 실행 결과다
- `grep -rn "execute(\|text(" backend/src`: `db.py:19`의 고정 문자열 `PRAGMA foreign_keys=ON` 하나뿐. 문자열 조합 SQL 없음
- `git grep -nE "(secret|password|token)\s*=\s*['\"]"`: 테스트 픽스처 2건(`test_t05_auth.py:113`, `test_passwords.py:31`)뿐이고 실제 비밀값 아님. `.env.example`에 4개 변수(DATABASE_URL, SESSION_COOKIE_SECURE, API_PROXY_TARGET, VITE_API_BASE_URL)가 모두 있고 값은 비어 있음(STATUS "열린 이슈"의 확인 필요 항목 해소)

## 이월 항목(M1 보안 Minor) 해소 확인
| 항목 | 결과 | 증거 |
|---|---|---|
| 본문 크기 상한 | 해소 | `api/middleware.py:54-71`. 70KB 본문 → 413, `Transfer-Encoding: chunked` → 411, `Content-Length` 5000자리 → 413(500 아님, `test_huge_content_length_is_413_not_500`) |
| 보안 헤더 | 해소 | `config.py:9-13`, `middleware.py:88-98`, 500은 `errors.py:148-155`가 직접 붙임. 404·422 응답에서 CSP·X-Frame-Options·nosniff 확인, `test_unexpected_exception_500_has_security_headers` 통과. `/docs`, `/redoc`, `/openapi.json` → 404(`main.py:21`) |
| 이동 경로에 사용자 입력 금지 | 해소 | `navigate`/`<Link to>` 대상은 모두 고정 문자열이거나 서버가 준 숫자 템플릿(`PostListPage.tsx:63,71,75`, `PostDetailPage.tsx:94`, `PostEditPage.tsx:69`, `PostNewPage.tsx:16`). `?next=`류 없음. `LoginPage.tsx:40`의 `location.state`는 안내 문구 표시용 boolean일 뿐 이동 대상이 아님. 라우트 `:id`는 `parsePostId`(`utils/postId.ts`)를 통과한 number만 API 경로에 들어감 |
| CORS 미개방 | 해소 | `grep -rni "cors\|access-control"` 결과 0건. `Origin: https://evil.example` 프리플라이트 → 405, `Access-Control-*` 헤더 없음. 단순 GET에도 없음 |

## IDOR 확인 (S4)
- 서비스 계층 소유권 검사: `services/posts.py:99-106`(`ensure_author`), `update_post` 115-116, `delete_post` 130-131. 검증(`validate_post`)보다 먼저 실행돼 남의 글에는 내용 검증 결과도 새지 않음
- bobby가 alice 글(id=1)에 PUT·DELETE: `/api/posts/1`, `/1/`, `/%31`, `/1?x=1` → 모두 403. `/+1`, `/01`, `/1%00`, `/1.0` → 404. 공격 후 alice 글 내용 변화 없음
- 필드 바꿔치기: 작성·수정 본문에 `author_id`(bobby), `id`, `created_at`를 넣어도 무시됨(작성자 alice 유지, `PostWriteRequest`는 title·content만 받음)
- 메서드 우회: `X-HTTP-Method-Override: DELETE` 붙인 POST → 405, PATCH → 405
- 세션 위조·재사용: 임의 쿠키 → 401, 로그아웃한 토큰으로 PUT → 401
- 테스트: `test_api_posts.py::test_update_and_delete_by_other_user_is_403`(PUT·DELETE 모두, 잘못된 내용이어도 403), `test_update_and_delete_without_login_is_401`, `test_posts_service.py::test_update_post_by_other_user_is_forbidden_before_validation`, `::test_delete_post_by_other_user_is_forbidden`, 인수 `test_t12_posts_modify.py::test_ac24_*`
- CSRF(S8): text/plain DELETE, form-urlencoded POST → 415. SameSite=Lax 쿠키 유지(M1)

나머지 항목: S1·S2·S11·S13은 M1과 같고 이번 변경 없음(M1 r1 통과). S5는 페이지 크기 10 고정(`size=100000` 무시 → 10), `page` 5000자리 → 200 page=1, 글 길이는 `validation.py:58-83`, 본문은 64KiB 상한. S7은 `dangerouslySetInnerHTML`/`innerHTML`/`eval` 사용 0건(`main.test.tsx` 테스트 준비 코드만 있음), 글은 JSX 텍스트로 렌더링. S10은 잘못된 JSON에 422 오류 형식만 나가고 내부 정보 없음.

## 발견 사항
| # | 등급 | 위치 | 문제 | 수정 지시 | 담당 |
|---|---|---|---|---|---|
| 1 | Minor | frontend/package.json (react-router-dom 6.30.6) | npm audit moderate: GHSA-wrjc-x8rr-h8h6(`<Link>`/`useNavigate`에 역슬래시가 든 경로를 넘기면 외부 사이트로 이동하는 open redirect), GHSA-337j-9hxr-rhxg(SSR 하이드레이션 전용). 패치는 7.18.4 이상에만 있음. **지금은 악용할 수 없음**: 보안 조건 #1 때문에 이동 대상에 사용자 문자열이 들어가지 않고, SSR을 쓰지 않음. 재현 조건: 앞으로 누군가 `navigate(searchParams.get("next"))`처럼 사용자 입력을 이동 대상으로 쓰면 `?next=/\evil.example` 같은 값으로 외부 사이트로 보낼 수 있음 | 보안 조건 #1을 이후 마일스톤에서도 유지(02_design.md 공통 규칙으로 올리는 것을 권장). react-router v7 상향은 메이저 변경이므로 다음 마일스톤 설계 때 검토하고, 상향 전까지 audit 결과에 이 항목을 알려진 예외로 남김 | architect |
| 2 | Minor | frontend/package.json (vitest·@vitest/mocker·@vitest/coverage-v8 3.2.7) | npm audit moderate: GHSA-82fw-gwwq-j7x9(mocker redirect mock의 경로 탐색). 개발·테스트에서만 쓰고 운영 번들(`dist`)에는 들어가지 않음. 고친 버전은 vitest 5.x(메이저 변경) | 다음 마일스톤 설계 때 vitest 상향을 검토. 그 전까지는 신뢰하지 않는 테스트 코드를 돌리지 않음 | architect |

## 참고 (판정과 무관, PM 최종 검수 때)
- `README.md`가 아직 없다. 02_design.md "배포" 절의 운영 가정(정적 HTML 응답의 CSP·X-Frame-Options, 프록시 본문 상한, `/api`만 전달, `SESSION_COOKIE_SECURE=true`)을 README "운영 안내"에 옮겨 적어야 한다. API 응답 헤더는 백엔드가 붙이지만, SPA HTML의 클릭재킹 방지는 이 안내에 달려 있다.
