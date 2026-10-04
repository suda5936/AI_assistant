"""요청 형식·크기를 검사하고 보안 헤더를 붙이는 미들웨어."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from board.config import SECURITY_HEADERS
from board.errors import error_body

STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
API_PREFIX = "/api/"
JSON_MEDIA_TYPE = "application/json"


def register_json_only_middleware(app: FastAPI) -> None:
    """/api/ 아래 상태 변경 요청이 JSON이 아니면 415 오류 본문을 응답한다."""

    @app.middleware("http")
    async def json_only(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in STATE_CHANGING_METHODS and request.url.path.startswith(API_PREFIX):
            media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if media_type != JSON_MEDIA_TYPE:
                return JSONResponse(
                    status_code=415,
                    content=error_body("unsupported_media_type", "JSON 형식으로 요청해 주세요."),
                )
        return await call_next(request)


def _is_ascii_digits(raw: str) -> bool:
    """비어 있지 않은 ASCII 10진 숫자 문자열인지 검사한다."""
    return bool(raw) and raw.isascii() and raw.isdigit()


def _length_required() -> JSONResponse:
    """411 오류 응답을 만든다."""
    return JSONResponse(
        status_code=411,
        content=error_body("length_required", "요청 본문의 길이를 알 수 없습니다."),
    )


def _payload_too_large() -> JSONResponse:
    """413 오류 응답을 만든다."""
    return JSONResponse(
        status_code=413,
        content=error_body("payload_too_large", "요청 본문이 너무 큽니다."),
    )


def _check_body_length(request: Request, max_bytes: int) -> JSONResponse | None:
    """헤더만 보고 411·413 응답을 만든다. 통과하면 None."""
    if "transfer-encoding" in request.headers:
        return _length_required()
    lengths = request.headers.getlist("content-length")
    if not lengths:
        return None
    if len(lengths) > 1:
        return _length_required()
    raw = lengths[0].strip()
    if not _is_ascii_digits(raw):
        return _length_required()
    digits = raw.lstrip("0")
    if len(digits) > len(str(max_bytes)):
        return _payload_too_large()
    if int(digits or "0") > max_bytes:
        return _payload_too_large()
    return None


def register_body_limit_middleware(app: FastAPI, max_bytes: int) -> None:
    """/api/ 아래 상태 변경 요청의 본문 크기를 헤더만 보고 제한한다 (411, 413)."""

    @app.middleware("http")
    async def body_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in STATE_CHANGING_METHODS and request.url.path.startswith(API_PREFIX):
            rejection = _check_body_length(request, max_bytes)
            if rejection is not None:
                return rejection
        return await call_next(request)


def register_security_headers_middleware(app: FastAPI) -> None:
    """모든 응답에 보안 헤더 3개를 설정한다 (이미 있으면 덮어쓴다)."""

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response
