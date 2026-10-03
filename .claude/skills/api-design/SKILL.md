---
name: api-design
description: 서비스의 API 계약과 DB 설계 규칙. REST 엔드포인트, 요청·응답 스키마, 오류 형식, 인증·권한, SQLAlchemy 모델, 마이그레이션, 백엔드 계층 구조. architect가 서비스를 설계할 때, developer가 백엔드·프론트엔드를 구현할 때, reviewer·security-reviewer가 검토할 때 사용한다.
---

# API·DB 설계 규칙

## 원칙: 계약 우선
API 계약(엔드포인트, 스키마, 오류)을 **설계 단계에서 먼저 확정**한다. 백엔드와 프론트엔드 태스크는 이 계약만 보고 따로 개발하고, 계약이 바뀌면 architect가 설계 문서부터 고친다.

## 1. 계약 작성 형식 (02_design.md의 "API 계약")
```markdown
### POST /api/posts  — 게시글 작성
- 인증: 필요
- 요청: `{ "title": string(1~100), "body": string(1~5000) }`
- 응답 201: `Post`
- 오류: 401 unauthenticated, 422 validation_error
- 관련 AC: AC-8, AC-9

#### 스키마
Post = { "id": int, "title": string, "body": string, "author": UserPublic, "created_at": string(ISO 8601, UTC) }
```
- 모든 엔드포인트에 관련 AC를 적는다. AC 추적표와 함께 빠진 요구가 없는지 확인한다.

## 2. REST 규칙
- 경로는 `/api/` 아래 복수형 명사: `/api/posts`, `/api/posts/{id}`.
- 상태 코드: 200 조회·수정, 201 생성, 204 삭제, 400 잘못된 요청, 401 미인증, 403 권한 없음, 404 없음, 409 충돌(중복), 422 검증 실패.
- 목록은 페이지네이션: `?page=1&size=20` (size 최대 100), 응답 `{ "items": [...], "total": int, "page": int, "size": int }`.
- 시간은 UTC ISO 8601 문자열.

## 3. 오류 형식 (모든 엔드포인트 공통)
```json
{ "error": { "code": "post_not_found", "message": "게시글을 찾을 수 없습니다." } }
```
- `code`는 영문 snake_case로 고정해 프론트엔드와 테스트가 분기할 수 있게 한다. `message`는 사용자에게 보여줄 한국어.
- FastAPI의 기본 검증 오류(422)도 이 형식으로 바꾸는 예외 처리기를 둔다 (`code: "validation_error"`, 필드별 상세는 `details`).
- 500 오류에 스택 트레이스나 내부 정보를 노출하지 않는다.

## 4. 인증과 권한
- 로그인 성공 시 서버 세션을 만들고 HttpOnly, SameSite=Lax 쿠키로 세션 ID를 보낸다. 세션 ID는 `secrets.token_urlsafe(32)` 이상.
- 비밀번호는 해시로만 저장한다 (scrypt 또는 argon2). 로그인 실패 메시지는 아이디·비밀번호 중 무엇이 틀렸는지 구분하지 않는다.
- **소유권 검사**: 남의 리소스를 수정·삭제하려 하면 403. 권한 검사는 서비스 계층에서 하고, 각 엔드포인트마다 "다른 사용자로 시도하는" 테스트를 둔다.
- 쿠키 인증을 쓰므로 상태를 바꾸는 요청(POST/PUT/PATCH/DELETE)은 `Content-Type: application/json`만 받는다 (CSRF 완화).

## 5. 백엔드 계층
```
backend/src/<패키지>/
├── main.py          # FastAPI 앱 생성, 라우터·예외 처리기 등록
├── config.py        # 환경변수 설정 (pydantic-settings 또는 os.environ)
├── db.py            # 엔진, 세션
├── models/          # SQLAlchemy 모델
├── schemas/         # Pydantic 요청·응답 스키마 (계약과 1:1)
├── services/        # 비즈니스 로직, 권한 검사 (HTTP를 모른다)
└── api/             # 라우터 (요청 검증 → 서비스 호출 → 응답)
```
- 의존 방향: `api → services → models`. 서비스는 FastAPI 객체(Request 등)를 받지 않는다.
- 라우터에 비즈니스 로직을 쓰지 않는다.

## 6. DB
- SQLAlchemy 2.x 스타일(`Mapped`, `mapped_column`). 문자열 조합 SQL 금지 (SQL 인젝션).
- 스키마를 바꿀 때마다 Alembic 마이그레이션을 만든다. 테스트는 마이그레이션이 아니라 메타데이터로 만든 임시 SQLite DB를 쓴다.
- 모든 테이블에 `id`, `created_at`. 자주 조회하는 외래 키와 유니크 컬럼에 인덱스.
- 삭제 정책(물리 삭제 / 소프트 삭제)과 연관 데이터 처리(댓글 등)를 설계 문서에 명시한다.

## 7. 테스트
- 엔드포인트마다: 정상, 검증 실패, 미인증(401), 남의 리소스(403), 없음(404).
- 테스트는 `TestClient`와 테스트 전용 DB를 쓰고 서로 독립적이어야 한다 (테스트 간 데이터 공유 금지).
