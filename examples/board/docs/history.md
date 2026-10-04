# 진행 기록

## M1: 회원가입·로그인 (완료 2026-10-03)
- 통합 검증: docs/qa/M1-int-r1.md (통과, E2E 20개, AC-1~AC-10 회귀)
- 보안 리뷰: docs/reviews/security-M1-r1.md (통과, Minor 3건은 M2 설계에 반영)
- make audit: high 이상 0건 (moderate 5건: vitest 계열, react-router) / make coverage: 백엔드 98.81%, 프론트 100%

| ID | 내용 | 반려 | 문서 |
|---|---|---|---|
| T-01 | 백엔드 환경·앱 골격 | 0 | reviews/T-01-r1, qa/T-01-r1 |
| T-02 | 공통 오류 처리 (예외명 *Error 접미사로 설계 수정) | 0 | reviews/T-02-r1, qa/T-02-r1 |
| T-03 | 모델·마이그레이션·비밀번호 해시 | 0 | reviews/T-03-r1, qa/T-03-r1 |
| T-04 | 회원가입 | 0 | reviews/T-04-r1, qa/T-04-r1 |
| T-05 | 로그인·로그아웃·me | 1 (로그인 타이밍 차이) | reviews/T-05-r1·r2, qa/T-05-r1 |
| T-06 | 프론트 환경·실행 타깃 (vite 6, vitest 3, pytest 9로 audit 통과) | 1 (pytest 하한 불일치) | reviews/T-06-r1·r2, qa/T-06-r1 |
| T-07 | 프론트 API 계층·인증 상태 | 0 | reviews/T-07-r1, qa/T-07-r1 |
| T-08 | 가입·로그인 화면 | 1 (main.tsx Router·AuthProvider 누락) | reviews/T-08-r1·r2, qa/T-08-r1 |
| T-09 | 헤더·홈·404 | 1 (로그아웃 실패 처리 설계 충돌 → 설계 수정) | reviews/T-09-r1·r2, qa/T-09-r1 |

## 결정 기록 (M1)
- ADR 0001-auth-storage 승인(대표, 대행 기록).
- 의존성 상향(vite 6.4.3, vitest 3.2.7, pytest 9)은 표준 ADR이 메이저를 고정하지 않아 PM이 대행 승인.
- 로그아웃 실패 시: 로그인 유지 + 재시도 안내(401은 성공 처리).
- 가입 비밀번호에 인코딩 불가 문자 → 422 (명세 "세부 보강").

## 미처리 항목 (M2로 이월)
- backend/tests conftest의 테이블 직접 나열 → M2 첫 백엔드 태스크에서 Base.metadata.create_all로
- AuthProvider.test Minor 2건(logout reject 확인), 보안 Minor(요청 본문 크기 상한, 보안 헤더, M2 설계 조건)

## M2 게시글 (완료)
### 태스크
| ID | 내용 | 상태 | 반려 횟수 | 최근 문서 |
|---|---|---|---|---|
| T-10 | 게시글 모델·마이그레이션 (+conftest create_all 복구) | 완료 (커밋) | 0 | docs/reviews/T-10-r1.md, docs/qa/T-10-r1.md (둘 다 통과). Minor 2건은 T-11 때 처리 |
| T-11 | 게시글 서비스 | 완료 (커밋) | 1 | docs/reviews/T-11-r1.md (반려), T-11-r2.md (통과), docs/qa/T-11-r1.md (통과). parse_page 앞자리 0 규칙은 T-12에서 코드 반영(설계 수정됨) |
| T-12 | 게시글 API (+parse_page 앞자리 0 규칙) | 완료 (커밋) | 1 | docs/reviews/T-12-r1.md (반려), T-12-r2.md (통과), docs/qa/T-12-r1.md (통과). T-13 QA에서 확인할 항목은 qa 문서에 기록됨 |
| T-13 | 요청 보호(본문 크기 상한, 보안 헤더, /docs 끔) | 완료 (커밋) | 1 | docs/reviews/T-13-r1 (반려: 청크 전송 우회)·r2 (통과), docs/qa/T-13-r1 (통과). Minor: developer 단언 정확화(T-14와 함께), architect .strip()·uvicorn 선거부 문구(병행 처리 중) |
| T-14 | 프론트 기반 (+AuthProvider.test Minor) | 완료 (커밋) | 0 | docs/reviews/T-14-r1.md, docs/qa/T-14-r1.md (둘 다 통과). Minor 2건(posts.test lastCall, datetime 시간대 없는 입력)은 T-15 때 처리 |
| T-15 | 목록 화면 | 완료 (커밋) | 0 | docs/reviews/T-15-r1.md, docs/qa/T-15-r1.md (둘 다 통과). Minor 3건 이월: developer 2건(PostListPage.test 186-188 waitFor 무효, 184 act 경고)은 T-16 때, architect 1건(formatKst UTC 규칙)은 M2.md에 반영 완료(2026-10-04) |
| T-16 | 상세·삭제 화면 | 완료 (커밋) | 0 | docs/reviews/T-16-r1.md, docs/qa/T-16-r1.md (둘 다 통과). Minor 2건 이월(developer): PostDetailPage.test 76 "남의 글" 대기 조건 약함, PostDetailPage.tsx 40-44 :id 변경 시 이전 글·버튼 한 렌더 노출·deleting 미초기화 → T-17 때 처리 |
| T-17 | 글쓰기 (+T-16 이월 Minor 2건) | 완료 (커밋) | 0 | docs/reviews/T-17-r1.md, docs/qa/T-17-r1.md (둘 다 통과). Minor 1건 이월(developer, T-18 때): PostDetailPage.test 121-150 :id 변경 테스트가 수정 전 코드도 통과할 가능성(act가 재렌더까지 끝낸 뒤 단언). |
| T-18 | 글 수정 (+T-17 이월 Minor 1건) | 완료 (커밋) | 0 | docs/reviews/T-18-r1.md, docs/qa/T-18-r1.md (둘 다 통과). Minor 1건(developer): PostEditPage.test 113-118 "세션 확인 중" 테스트에 getPost 미호출 단언 추가 — 이후 프론트 변경 때 또는 M2 통합 검증 전 보강 태스크로. |
| T-19 | 테스트 보강(T-18 이월 Minor: PostEditPage.test getPost 미호출 단언) | 완료 (커밋) | 0 | 소 규모: developer → 훅 → PM make check 통과. 근거: 테스트 한 줄 추가, 설계 범위 안 |

- 통합 검증: docs/qa/M2-int-r1.md 통과(AC 25/25, make e2e 42개), docs/reviews/security-M2-r1.md 통과, make coverage 통과.
- 설계 보강: formatKst 오프셋 없는 입력은 UTC 간주(M2.md 반영).
