판정: 통과

# M2 통합 검증 1회차 (QA)

구현 코드(frontend/src, backend/)는 읽지 않았다. 기준은 docs/01_spec.md와 docs/milestones/M2.md "통합 검증 시나리오"다.

## 실행 결과
| 구분 | 명령 | 결과 |
|---|---|---|
| 백엔드 단위·인수 | `make -C backend test` (약 3분 23초) | 674개 통과, 0 실패 (경고 1: httpx TestClient 폐기 예고, 무해) |
| 프론트 인수 vitest | `cd frontend && npx vitest run --config ../tests/acceptance/frontend/<설정>` 6개 | vitest.config.ts(T-07) 18, t14 52, t15 13, t16 10, t17 10, t18 9 = 112개 전부 통과 |
| E2E | `make e2e` (실서버 백엔드 8001, 프론트 5174) | 42개 통과 (M1 회귀 26 + M2 신규 16), 45초 |

## 통합 검증 시나리오 결과
| # | 시나리오 | 확인 위치 | 결과 |
|---|---|---|---|
| 1 | 빈 목록 (AC-11) | e2e ui `M2-posts.spec.ts`(page.route 빈 응답), 백엔드 인수(새 DB) | 통과 |
| 2 | 비로그인 글쓰기 차단 (AC-17) | e2e ui(`/`, `/posts/new`), e2e api(401, total 불변) | 통과 |
| 3 | 작성·검증 (AC-18~20) | e2e ui(빈 제목, 101자, 100자·여러 줄), e2e api 경계값 | 통과 |
| 4 | 상세 표시 (AC-15) | e2e ui(비로그인 상세, 시각 = API UTC + 9시간) | 통과 |
| 5 | 목록·페이지 (AC-12~14) | e2e ui(11개 추가, 최신순, 다음, page=0·-1·abc·99999), total=10 응답에서 nav 없음 | 통과 |
| 6 | XSS (AC-25) | e2e ui(dialog 0회, 글자 그대로), e2e api | 통과 |
| 7 | 수정 (AC-21) | e2e ui(초기값, 공백 내용 거부, 저장 후 상세·목록 반영) | 통과 |
| 8 | 권한 화면 (AC-23) | e2e ui(B, 비로그인, 목록 버튼 없음, B의 edit 직접 진입) | 통과 |
| 9 | 권한 API (AC-24) | e2e api(B의 PUT·DELETE 403, 빈 제목 PUT도 403, 비로그인 401, 내용 불변) | 통과 |
| 10 | 삭제 (AC-22, AC-16) | e2e ui(취소 유지, 수락 이동, 404 안내, abc·0·99999999) | 통과 |
| 11 | 요청 보호 | e2e api(65537바이트 413, CL+TE chunked 2MB 411·사용자 미생성, 비정상 길이 헤더는 400, 보안 헤더, /docs·/openapi.json 404, DELETE text/plain 415, CORS 헤더 없음) | 통과 |
| 12 | M1 회귀 | e2e M1 스펙 26개, 백엔드·프론트 M1 인수 | 통과 |

## STATUS 열린 이슈 보완 확인
- [QA 한계] "남의 글 수정 폼 저장 시 403": 통과. 사용자 A로 수정 폼을 연 뒤(화면은 A 상태) 같은 브라우저 컨텍스트의 쿠키를 B 세션으로 바꾸고 저장하면, 폼 위 alert에 "본인이 작성한 글만 수정하거나 삭제할 수 있습니다."가 보이고 URL은 `/edit`에 머물며 저장 버튼이 다시 활성화되고 글은 변하지 않았다. 삭제도 같은 방식으로 403 안내와 글 유지를 확인했다(`ui/M2-delete.spec.ts`). 스크린샷: `tests/e2e/screenshots/m2-save-403.png`, `m2-delete-403.png`.
- [QA 한계] "아무것도 안 바꾸고 저장": 통과. 수정 폼에서 변경 없이 저장하면 상세로 이동하고, 제목·내용·작성 시각(API 응답 전체)이 저장 전과 동일하며 목록에도 그대로 보인다. 스크린샷: `m2-edit-nochange.png`.
- [M2 통합 검증 때] 프론트 인수 vitest 6개 설정을 각각 실행해 전부 통과했다. 이 테스트는 `make check`에 포함되지 않으므로 계속 별도 실행이 필요하다.

## 발견 사항
| # | 등급 | 위치 | 문제 | 수정 지시 | 담당 |
|---|---|---|---|---|---|
| - | - | - | 결함 없음 | - | - |

관찰(결함 아님):
- 비정상 `Content-Length`·`Transfer-Encoding: identity`·값이 다른 중복 `Content-Length`는 서버(h11)가 앱에 닿기 전에 400으로 거부했다(서버 로그 "Invalid HTTP request received" 4건). M2.md 설계(400 또는 411/413 허용)와 일치한다.
- 403 저장 시나리오는 UI 정상 흐름으로는 재현할 수 없어(소유자만 폼 진입 가능) 세션 쿠키 교체로 실제 서버에서 만들었다. 서버 응답과 화면 처리를 실제로 통과한 결과다.
- 시나리오 1(정확히 0개)과 정확히 10·11개 경계는 공유 E2E DB 때문에 UI에서는 page.route 또는 상대값으로 확인했고, 정확한 개수는 백엔드 인수 테스트(새 DB)가 맡는다(설계 방침대로).

## AC 확인 (AC-1 ~ AC-25 회귀)
| AC | 테스트 | 결과 |
|---|---|---|
| AC-1~AC-10 (M1) | tests/acceptance/test_t0*.py, tests/e2e/api/M1-auth.spec.ts, tests/e2e/ui/M1-*.spec.ts | 통과 |
| AC-11 | tests/acceptance/test_t12_posts_api.py 등, e2e ui `시나리오1 AC-11` | 통과 |
| AC-12, AC-13 | 백엔드 인수 test_t11/t12, e2e ui `시나리오5 AC-12 AC-13 AC-14`, `AC-13: total=10` | 통과 |
| AC-14 | 백엔드 인수, e2e api `AC-14`, e2e ui 시나리오5 | 통과 |
| AC-15 | e2e ui `시나리오3·4 ... AC-15` | 통과 |
| AC-16 | e2e api `AC-16 AC-22`, e2e ui `시나리오10` | 통과 |
| AC-17 | e2e api `시나리오2`, e2e ui `시나리오2` | 통과 |
| AC-18 | e2e ui `시나리오3·4` | 통과 |
| AC-19, AC-20 | e2e ui `시나리오3·4`, e2e api `AC-19 AC-20` | 통과 |
| AC-21 | e2e ui `시나리오7`, `보완 AC-21` | 통과 |
| AC-22 | e2e ui `시나리오10`, e2e api `AC-16 AC-22` | 통과 |
| AC-23 | e2e ui `시나리오8` | 통과 |
| AC-24 | e2e api `시나리오9`, e2e ui `보완 AC-24`(저장·삭제 403) | 통과 |
| AC-25 | e2e ui `시나리오6`, e2e api `AC-25` | 통과 |

AC 25개 중 25개 통과.

## 작성한 파일
- tests/e2e/api/M2-posts.spec.ts
- tests/e2e/ui/M2-posts.spec.ts
- tests/e2e/ui/M2-delete.spec.ts
