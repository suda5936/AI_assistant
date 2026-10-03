---
name: frontend-standards
description: 프론트엔드(React + TypeScript + Vite) 코딩 규칙. 컴포넌트 구조, 타입, API 호출, 상태·오류 처리, 접근성, 보안, 테스트. 프론트엔드 코드를 설계·구현·리뷰할 때 적용한다. [자동] 규칙은 훅(eslint, prettier, tsc, 금지 패턴)이 검사한다.
---

# 프론트엔드 규칙 (React + TypeScript)

공통 원칙(이름, 구조, 금지된 꼼수)은 coding-standards를 따르고, 이 문서는 프론트엔드에만 해당하는 규칙이다.

## 1. 타입과 스타일
- [자동] `tsconfig.json`은 `"strict": true`. `tsc --noEmit`이 통과해야 한다.
- [자동] eslint(typescript-eslint, react-hooks 규칙)와 prettier를 통과한다.
- [자동] `any`를 쓰지 않는다 (`@typescript-eslint/no-explicit-any`). 모르는 값은 `unknown`으로 받고 좁힌다.
- [자동] `console.log`, `debugger`를 남기지 않는다. 검사를 끄는 주석(`eslint-disable`, `@ts-ignore`)은 금지된 꼼수다.
- [판단] 컴포넌트는 `PascalCase.tsx`, 훅은 `useSomething.ts`, 그 외는 `camelCase.ts`.

## 2. 구조
```
frontend/src/
├── api/          # 백엔드 호출은 여기서만 (client.ts + 기능별 파일)
├── components/   # 재사용 UI
├── pages/        # 라우트 단위 화면
├── hooks/        # 커스텀 훅
└── types/        # API 계약에 대응하는 타입
```
- [판단] 컴포넌트 하나는 한 가지 역할. 150줄을 넘으면 나눈다.
- [판단] 화면 컴포넌트(pages)에서 `fetch`를 직접 부르지 않는다. 반드시 `api/`의 함수를 쓴다.

## 3. API 호출
- [판단] `api/client.ts` 하나가 기본 URL, `credentials: "include"`(세션 쿠키), JSON 변환, 오류 변환을 맡는다.
- [판단] 응답·요청 타입은 설계 문서의 API 계약과 **필드 이름까지 일치**해야 한다 (`types/`).
- [판단] 오류 응답(`{"error": {"code", "message"}}`)은 `ApiError`로 바꿔 던지고, 화면은 `message`를 사용자에게 보여준다.

## 4. 상태와 화면
- [판단] 데이터를 불러오는 화면은 **로딩, 오류, 빈 목록, 정상** 네 가지 상태를 모두 그린다.
- [판단] 폼은 제출 중 버튼을 비활성화해 중복 제출을 막고, 서버 검증 오류를 필드 옆에 보여준다.
- [판단] 로그인이 필요한 화면은 세션 확인 후 미로그인이면 로그인 화면으로 보낸다.

## 5. 접근성 (E2E 테스트의 기반)
- [판단] 입력에는 `<label>`을 연결하고, 버튼은 `<button>`을 쓴다. 클릭 가능한 `div` 금지.
- [판단] 의미 있는 요소는 역할과 이름으로 찾을 수 있어야 한다. Playwright가 `getByRole`, `getByLabel`로 찾는다.
- [판단] 테스트용 선택자가 꼭 필요하면 `data-testid`를 쓴다 (CSS 클래스로 찾지 않는다).

## 6. 보안
- [자동] `dangerouslySetInnerHTML` 금지 (eslint `react/no-danger`).
- [판단] 토큰이나 비밀값을 `localStorage`에 저장하지 않는다. 인증은 HttpOnly 쿠키 세션 (docs/adr/0001).
- [판단] API 기본 URL 등 설정은 `import.meta.env.VITE_*`로 읽고 `.env.example`에 적는다. 비밀값은 프론트엔드에 두지 않는다.

## 7. 테스트 (vitest + Testing Library)
- [판단] 컴포넌트 테스트는 `*.test.tsx`로 같은 폴더에 둔다.
- [판단] 구현 세부(state 이름 등)가 아니라 사용자가 보는 결과(텍스트, 역할)를 검증한다.
- [판단] API는 `api/` 함수를 mock해서 테스트한다. 실제 서버는 E2E에서 확인한다.
