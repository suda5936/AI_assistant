---
name: security-checklist
description: 서비스 보안 점검표. 인증, 세션, 권한(남의 데이터 접근), 입력 검증, 인젝션, XSS, CSRF, 비밀값, 오류 노출, 의존성 취약점을 항목별 확인 방법과 함께 정리했다. security-reviewer가 마일스톤 보안 리뷰를 할 때, architect·developer가 인증·권한을 설계·구현할 때 사용한다.
---

# 보안 점검표

판정과 문서 형식은 review-checklist를 따른다 (첫 줄 `판정: 통과|반려`, Critical/Major면 반려).
각 항목은 **확인 방법**대로 증거를 남긴다: 코드 위치(`파일:줄`), 실행한 명령과 결과, 또는 그 항목을 검증하는 테스트 이름.

| # | 항목 | 확인 방법 | 위반 시 |
|---|---|---|---|
| S1 | **비밀번호 저장** | 해시(scrypt/argon2)로만 저장하는지 모델·서비스 코드 확인. 평문, MD5, SHA-1 금지 | Critical |
| S2 | **세션** | 세션 ID가 `secrets` 기반 32바이트 이상인지, 쿠키가 HttpOnly·SameSite=Lax인지, 로그아웃 시 서버 세션이 삭제되는지 | Critical |
| S3 | **인증 누락** | 인증이 필요한 모든 엔드포인트(API 계약 표의 "인증: 필요")에 인증 의존성이 붙어 있는지 라우터를 하나씩 대조. 미인증 401 테스트가 있는지 | Critical |
| S4 | **권한(IDOR)** | 수정·삭제·비공개 조회에서 소유자 확인을 하는지 서비스 코드 확인. "다른 사용자로 시도 → 403" 테스트가 엔드포인트마다 있는지 | Critical |
| S5 | **입력 검증** | 모든 요청 본문·쿼리에 Pydantic 스키마와 길이·범위 제한이 있는지. 페이지 크기 상한이 있는지 | Major |
| S6 | **SQL 인젝션** | `grep -rn "execute(\|text(" backend/src`로 문자열 조합 SQL이 없는지 | Critical |
| S7 | **XSS** | 프론트엔드에 `dangerouslySetInnerHTML`, `innerHTML` 사용이 없는지. 사용자 입력이 React 텍스트로만 렌더링되는지 | Critical |
| S8 | **CSRF** | 상태를 바꾸는 요청이 JSON만 받는지, SameSite 쿠키인지, CORS가 `*`+credentials가 아닌지 | Major |
| S9 | **비밀값** | 코드·설정·테스트에 실제 비밀값이 없는지 (`git grep -nE "(secret|password|token)\s*=\s*['\"]"`). `.env.example`에 모든 변수가 있고 실제 값은 없는지 | Critical |
| S10 | **오류 노출** | 500 응답에 스택 트레이스·SQL·경로가 없는지. 로그인 실패 메시지가 계정 존재 여부를 드러내지 않는지 | Major |
| S11 | **민감 정보 로그** | 로그에 비밀번호, 세션 ID, 토큰을 남기지 않는지 | Major |
| S12 | **의존성 취약점** | `make audit` (pip-audit, npm audit --audit-level=high) 실행 결과. high 이상이 있으면 | Major |
| S13 | **무차별 대입** | 로그인 시도 제한이 명세에 있으면 구현 확인. 명세에 없으면 Minor로 "제안"만 | Minor |

## 리뷰 절차 (security-reviewer)
1. `docs/02_design.md`의 API 계약과 인증 방식, 해당 마일스톤 문서를 읽는다.
2. 이번 마일스톤에서 추가·변경된 엔드포인트 목록을 만든다.
3. S1~S13을 순서대로 확인한다. 이번 마일스톤과 무관한 항목은 "해당 없음"으로 한 줄만.
4. `make audit`를 실행한다. 실행할 수 없으면(네트워크 등) 그 사실을 기록한다.
5. `docs/reviews/security-M<n>-r<k>.md`에 결과를 쓴다. 발견 사항마다 **재현 방법**(어떤 요청을 보내면 무엇이 되는지)과 수정 지시를 적는다.
