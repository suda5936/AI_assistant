# 실전 결과물

하네스(`/ship`)로 실제로 만든 프로젝트 두 개입니다. 각 프로젝트의 git 저장소에 커밋된 파일을 그대로 옮겼고, 커밋 이력은 `COMMITS.md`에 있습니다.
사람은 요청서를 주고, 질문에 답하고(이번에는 대행), 결과를 확인하기만 했습니다. 명세·설계·코드·테스트·리뷰 문서는 모두 에이전트가 썼습니다.

## 1. test_project — 할 일 관리 CLI (로드맵 4-5)

| 항목 | 값 |
|---|---|
| 요청 | "터미널에서 쓰는 간단한 할 일 관리 프로그램" (한 문단) |
| 명세 | AC 10개, 마일스톤 1개 |
| 태스크 | 5개 (T-05는 통합 검증에서 발견된 결함 수정) |
| 에이전트 호출 | 20회 (architect 2, developer 6, reviewer 6, qa 6) |
| 리뷰 / QA 반려 | 리뷰 1회 (T-02), 통합 검증 1회 |
| 테스트 | 291개 통과 |
| 소요 | 약 20분, API 환산 비용 약 $6 |

볼 곳: [`docs/01_spec.md`](test_project/docs/01_spec.md), [`docs/milestones/M1.md`](test_project/docs/milestones/M1.md), [`docs/reviews/T-02-r1.md`](test_project/docs/reviews/T-02-r1.md)(반려 사례)

## 2. board — 사내 게시판 웹 서비스 (로드맵 8-1, 8-2)

| 항목 | 값 |
|---|---|
| 요청 | 자유 형식 요청서 (기능 6개, 기타 요구 3줄) → [`docs/00_request.md`](board/docs/00_request.md) |
| 명세 | AC 25개, 마일스톤 2개 (M1 회원가입·로그인, M2 게시글), PM이 찾은 질문 11개 |
| 스택 | FastAPI + SQLAlchemy + SQLite / React + TypeScript + Vite / Playwright |
| 태스크 | 20개 (M1 9개, M2 9개 + 보강 1개 + D3 수정 1개) |
| 에이전트 호출 | 99회 (architect 17, developer 33, reviewer 27, qa 20, security-reviewer 2) |
| 리뷰 반려 | 8회 (모두 재작업 한도 3회 안에서 해결) |
| 통합 검증 | 마일스톤마다 qa(회귀 + E2E) + 보안 리뷰 + audit + coverage 통과 |
| 테스트 | 백엔드 674개, 프론트엔드 149개, E2E 42개 (스크린샷 포함) |
| 커버리지 | 백엔드 99.2%, 프론트엔드 lines 100% |
| 완료 기준 | D1~D7 모두 충족 (깨끗한 클론에서 `make setup` → `make check` 포함) |
| 소요 | 약 6.5시간(세션 중단 2회 후 재개), API 환산 비용 약 $52 |

볼 곳:
- 명세 변환: [`docs/00_request.md`](board/docs/00_request.md) → [`docs/01_spec.md`](board/docs/01_spec.md)
- 설계: [`docs/02_design.md`](board/docs/02_design.md) (API 계약, DB 스키마), [`docs/milestones/`](board/docs/milestones/)
- 리뷰 반려와 재작업: [`docs/reviews/`](board/docs/reviews/), 보안 리뷰 [`security-M1-r1.md`](board/docs/reviews/security-M1-r1.md)
- 통합 검증: [`docs/qa/M2-int-r1.md`](board/docs/qa/M2-int-r1.md), E2E 스크린샷 [`tests/e2e/screenshots/`](board/tests/e2e/screenshots/)
- 하네스 규칙 충돌을 스스로 찾아 해결한 기록: [`docs/adr/0002-project-lint-config.md`](board/docs/adr/0002-project-lint-config.md)

실행: `cd board && make setup && make dev` → http://127.0.0.1:5173 (Node 22, Python 3.11+)

## 하네스가 실전에서 잡은 것 (board 기준, `scripts/harness_report.py`)
- 파일 수정 393회 중 28회를 자동 검사가 즉시 되돌려 보냄 (정의 안 된 이름 F821, 하드코딩 비밀값 의심, 미사용 import, 검사 끄기 주석 5회 등)
- 품질 게이트가 "끝났다"는 선언을 9회 거부
- 역할 밖 쓰기·셸 명령 22회 차단 (qa가 셸로 테스트 파일을 쓰려던 시도 → Write 도구로 전환해 검사를 거침)
- 에이전트가 하네스 자체의 버그 2건을 찾아 대표에게 보고 (lessons L-17, L-19)

## 한계
- 화면은 요청서의 "디자인은 신경 안 써도 됨"에 따라 스타일이 없습니다.
- 명세의 미해결 질문과 ADR은 이번 실전에서 대표 대신 승인(대행)했습니다. 실제 사용에서는 사용자가 답합니다.
- 비용은 실행 로그의 API 환산값입니다 (구독 요금제 사용량과 다를 수 있음).
