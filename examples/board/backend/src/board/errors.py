"""앱 예외 계층과 예외 처리기."""

import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from board.config import SECURITY_HEADERS

logger = logging.getLogger(__name__)

VALIDATION_MESSAGE = "입력값을 확인해 주세요."
FIELD_FORMAT_MESSAGE = "형식이 올바르지 않습니다."


@dataclass(frozen=True)
class FieldError:
    """필드 하나의 검증 오류."""

    field: str
    message: str


class AppError(Exception):
    """서비스가 던지는 앱 예외의 기반 클래스."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "일시적인 오류가 발생했습니다."


class ValidationFailedError(AppError):
    """필드 검증 실패."""

    status_code = 422
    code = "validation_error"
    message = VALIDATION_MESSAGE

    def __init__(self, details: list[FieldError]) -> None:
        super().__init__(self.message)
        self.details = details


class UsernameTakenError(AppError):
    """이미 사용 중인 아이디."""

    status_code = 409
    code = "username_taken"
    message = "이미 사용 중인 아이디입니다."


class InvalidCredentialsError(AppError):
    """로그인 실패."""

    status_code = 401
    code = "invalid_credentials"
    message = "아이디 또는 비밀번호가 올바르지 않습니다."


class NotAuthenticatedError(AppError):
    """로그인이 필요함."""

    status_code = 401
    code = "unauthenticated"
    message = "로그인이 필요합니다."


class PostNotFoundError(AppError):
    """없는 글, 또는 형식이 잘못된 글 ID."""

    status_code = 404
    code = "post_not_found"
    message = "게시글을 찾을 수 없습니다."


class ForbiddenError(AppError):
    """남의 글을 수정·삭제하려 함."""

    status_code = 403
    code = "forbidden"
    message = "본인이 작성한 글만 수정하거나 삭제할 수 있습니다."


def error_body(
    code: str, message: str, details: list[FieldError] | None = None
) -> dict[str, object]:
    """오류 응답 본문을 만든다. details가 None이면 키를 넣지 않는다."""
    body: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        body["details"] = [asdict(item) for item in details]
    return {"error": body}


def field_from_loc(loc: Sequence[str | int] | None) -> str:
    """loc에서 문자열인 요소 중 마지막 것을 돌려준다. 없으면 "body"."""
    if loc:
        for element in reversed(loc):
            if isinstance(element, str):
                return element
    return "body"


def _http_error_parts(status_code: int) -> tuple[str, str]:
    """HTTP 상태 코드에 대응하는 (code, message)를 돌려준다."""
    if status_code == 404:
        return "not_found", "요청한 경로를 찾을 수 없습니다."
    if status_code == 405:
        return "method_not_allowed", "허용되지 않은 요청 방식입니다."
    return "http_error", "요청을 처리할 수 없습니다."


async def _handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    details = exc.details if isinstance(exc, ValidationFailedError) else None
    return JSONResponse(
        status_code=exc.status_code, content=error_body(exc.code, exc.message, details)
    )


async def _handle_request_validation(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    details = [
        FieldError(field=field_from_loc(item.get("loc")), message=FIELD_FORMAT_MESSAGE)
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422, content=error_body("validation_error", VALIDATION_MESSAGE, details)
    )


async def _handle_http_exception(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code, message = _http_error_parts(exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, message),
        headers=getattr(exc, "headers", None),
    )


async def _handle_unexpected(_request: Request, _exc: Exception) -> JSONResponse:
    """처리되지 않은 예외를 500으로 바꾼다. 가장 바깥에서 실행되므로 보안 헤더를 직접 붙인다."""
    logger.exception("처리되지 않은 예외")
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "일시적인 오류가 발생했습니다."),
        headers=dict(SECURITY_HEADERS),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """AppError, RequestValidationError, HTTPException, Exception 처리기를 등록한다."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
