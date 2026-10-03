---
name: e2e-testing
description: 서비스의 실행 검증(E2E) 규칙. Playwright로 실제 백엔드·프론트엔드 서버를 띄워 API 시나리오와 브라우저 화면 시나리오를 검증하고 스크린샷을 남긴다. qa가 마일스톤 통합 검증을 할 때, architect·developer가 E2E 실행 환경(make e2e, 서버 포트, 프록시)을 설계·구현할 때 사용한다.
---

# E2E 검증 규칙

목표: "단위 테스트는 통과했는데 실제로 띄우면 안 되는" 문제를 잡는다 (완료 기준 D4).
**실제 서버**에 **실제 HTTP 요청과 실제 브라우저**로 사용자 시나리오를 실행한다.

## 역할 분담
| 누가 | 무엇을 |
|---|---|
| architect | 02_design.md "실행 방법"에 E2E용 포트·DB·서버 실행 명령을 정한다. 마일스톤 문서에 "통합 검증 시나리오"를 쓴다 |
| developer | 서버가 환경변수(DB 경로, 포트)로 설정되게 만들고, 프론트엔드 개발 서버가 `/api`를 백엔드로 프록시하게 하고, `make e2e` 타깃을 만든다 |
| qa | `tests/e2e/` 아래의 Playwright 설정·시나리오를 작성하고 실행해 판정한다 |

## 폴더 구조 (qa 소유)
```
tests/e2e/
├── package.json            # @playwright/test 만 의존 (이 환경의 브라우저에 맞춰 1.56.1 고정)
├── playwright.config.ts    # webServer로 백엔드·프론트엔드를 띄운다
├── api/                    # API 시나리오 (request 컨텍스트)
│   └── M1-auth.spec.ts
├── ui/                     # 브라우저 시나리오
│   └── M1-signup-login.spec.ts
└── screenshots/            # 시나리오 단계별 스크린샷 (커밋하지 않음)
```

## playwright.config.ts 기준
- `webServer` 배열로 백엔드와 프론트엔드를 **Playwright가 직접 띄우고 끈다.** 수동으로 서버를 띄우지 않는다.
  - 백엔드: E2E 전용 포트와 **매 실행마다 새로 만드는 E2E 전용 DB 파일** (예: `DATABASE_URL=sqlite:///./e2e.db`, 시작 전에 삭제)
  - 프론트엔드: 개발 서버를 E2E 포트로, `/api`는 백엔드로 프록시 (같은 출처라 쿠키가 그대로 동작)
  - `reuseExistingServer: false`, 충분한 `timeout`
- `use.baseURL`은 프론트엔드 주소, 실패 시 `trace: "retain-on-failure"`, `screenshot: "only-on-failure"`
- 브라우저는 chromium 하나, `workers: 1` (DB 공유로 인한 간섭 방지)

## 시나리오 작성
- 파일명에 마일스톤, 테스트 이름에 AC 번호: `test("AC-3: 중복 아이디로 가입하면 오류를 보여준다", ...)`
- 마일스톤 문서의 "통합 검증 시나리오"를 **사용자 흐름 그대로** 옮긴다. 예: 가입 → 로그인 → 글쓰기 → 목록에서 확인 → 로그아웃
- 요소는 `getByRole`, `getByLabel`, `getByText`로 찾는다. CSS 클래스로 찾지 않는다 (필요하면 `data-testid`).
- 테스트마다 고유한 데이터(예: `user_${Date.now()}`)를 써서 서로 영향을 주지 않게 한다.
- 고정 대기(`waitForTimeout`) 금지. `expect(...).toBeVisible()` 같은 자동 대기 단언을 쓴다.
- 핵심 단계마다 `page.screenshot({ path: "screenshots/<시나리오>-<단계>.png" })`로 증거를 남긴다.
- 권한 시나리오를 반드시 넣는다: 로그아웃 상태로 보호된 화면 접근, 다른 사용자의 리소스 수정 시도.

## API 시나리오
- `request` 픽스처로 실제 백엔드에 요청한다. 쿠키 세션이 이어지도록 같은 컨텍스트를 쓴다.
- 상태 코드와 오류 형식(`{"error": {"code", "message"}}`)까지 확인한다.

## 실행과 판정
- 실행: 프로젝트 루트에서 `make e2e` (내부적으로 `cd tests/e2e && npm ci && npx playwright test`).
- 결과 문서(`docs/qa/M<n>-int-r<k>.md`)에 시나리오별 통과/실패, 실패한 단계, 스크린샷 경로를 적는다.
- 서버가 뜨지 않으면 그 자체가 Critical 결함이다 (D4 위반). 테스트를 고쳐서 통과시키지 않는다.
