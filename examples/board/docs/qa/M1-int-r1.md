판정: 통과

# M1 통합 검증 1회차

## 실행 결과
- `make e2e` (실제 uvicorn:8001 + vite:5174 + chromium): 20개 통과, 0개 실패 (24.4s)
- 백엔드 단위+인수 `pytest -q ../tests/unit/backend ../tests/acceptance`: 313개 통과, 0개 실패 (경고 1건: starlette testclient httpx 사용 중단 안내, 무해)
- 프론트 인수 `tests/acceptance/frontend` (vitest): 18개 통과
- 구현 코드(frontend/src, backend/src)는 읽지 않았다. 명세·설계의 공개 인터페이스만 사용했다.
- 이번 회차에 추가한 E2E: `tests/e2e/api/M1-auth.spec.ts`(시나리오 9), `tests/e2e/ui/M1-login-anon.spec.ts`(시나리오 2, 5 보강)

## 시나리오별 결과
| # | 시나리오 | 테스트 | 결과 |
|---|---|---|---|
| 1 | 비로그인 `/` 헤더에 로그인·회원가입 링크, 아이디 없음 | ui/M1-header-session.spec.ts 시나리오1 | 통과 |
| 2 | 아이디 `ab`, 비번 7자, 공백뿐 아이디 사유 표시 (추가: 빈값, 21자, 허용 외 문자, 73자, 동시 오류) | ui/M1-signup-login.spec.ts AC-3, AC-4 외, ui/M1-login-anon.spec.ts 시나리오2 | 통과 |
| 3 | 가입 후 로그인 화면 이동 + 가입 완료 문구 | ui/M1-signup-login.spec.ts AC-1,2,6,7 | 통과 |
| 4 | 대문자로 재가입 시 "이미 사용 중인 아이디입니다." | 같은 파일 (원문 아이디 재가입도 확인) | 통과 |
| 5 | 틀린 비번·없는 아이디 동일 메시지, 헤더 비로그인, 쿠키 없음 | ui/M1-login-anon.spec.ts 시나리오5, M1-signup-login.spec.ts | 통과 |
| 6 | 로그인 후 `/` 이동, 헤더 아이디, 새로고침 유지 | ui/M1-header-session.spec.ts 시나리오6 | 통과 |
| 7 | 쿠키 `board_session` httpOnly=true, `document.cookie`에 없음 | M1-signup-login.spec.ts AC-1,2,6,7 (context.cookies, document.cookie) | 통과 |
| 8 | 로그아웃 후 비로그인 헤더, 이전 쿠키로 /me 401 `unauthenticated`, 새로고침 후에도 비로그인 | ui/M1-header-session.spec.ts 시나리오8 | 통과 |
| 8-1 | 로그아웃 500 → 아이디 유지 + role=alert 안내, route 해제 후 재시도 → 비로그인 (추가: 네트워크 abort, 401 응답, 요청 중 disabled·연타 1회) | ui/M1-header-session.spec.ts 시나리오8-1 외 3건 | 통과 |
| 9 | 가입·로그인·me 본문에 password/password_hash/해시 없음, text/plain 로그인 415, 오류 형식 `{error:{code,message}}` (409, 422, 401, 404, 잘못된 JSON 포함), 세션 독립성 | api/M1-auth.spec.ts 4건 | 통과 |
| 10 | DB 직접 조회: password_hash가 평문과 다르고 `scrypt$` 시작, 같은 비번 두 계정 해시 상이 | tests/acceptance/test_t03_passwords.py::test_ac5_hash_stored_in_db_is_not_plaintext, test_ac5_two_users_same_password_have_different_db_hashes | 통과 |

## AC 회귀 (AC-1 ~ AC-10)
| AC | 테스트 | 결과 |
|---|---|---|
| AC-1 | acceptance/test_t04_signup.py, e2e ui 시나리오3, api 시나리오9 | 통과 |
| AC-2 | acceptance/test_t04_signup.py, e2e ui 시나리오4, api 409 | 통과 |
| AC-3 | acceptance/test_t04_signup.py(7/8/72/73자, 서로게이트), e2e ui·api | 통과 |
| AC-4 | acceptance/test_t04_signup.py, e2e ui·api | 통과 |
| AC-5 | acceptance/test_t03_passwords.py::test_ac5_* | 통과 |
| AC-6 | acceptance/test_t05_auth.py, frontend t07, e2e 시나리오6 | 통과 |
| AC-7 | acceptance/test_t05_auth.py, e2e 시나리오5, api 시나리오9 | 통과 |
| AC-8 | acceptance/test_t05_auth.py, e2e 시나리오6 | 통과 |
| AC-9 | acceptance/test_t05_auth.py, e2e 시나리오8·8-1 | 통과 |
| AC-10 | acceptance/test_t05_auth.py, e2e 시나리오7·9 | 통과 |

## 발견 사항
- Critical/Major 없음. 서버 기동 실패 없음.
- 참고(Minor, 결함 아님): 브라우저 콘솔의 비로그인 `/api/auth/me` 401 리소스 로드 로그는 설계된 정상 응답이라 BOOT 테스트에서 제외했다.

## 스크린샷 (tests/e2e/screenshots/)
boot-home/signup/login, ac1-signed-up, ac2-duplicate, ac3-short, ac4-format, ac6-logged-in, ac7-wrong-pw, hdr-anon, hdr-logged-in, hdr-after-reload, hdr-logged-out, hdr-logout-failed, hdr-logout-retry-ok, s5-fail-wrongpw, s5-fail-nouser (.png)
