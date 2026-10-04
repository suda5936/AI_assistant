"""오류 응답 스키마. OpenAPI 문서의 responses 용이다."""

from pydantic import BaseModel


class FieldErrorOut(BaseModel):
    """필드별 오류."""

    field: str
    message: str


class ErrorDetail(BaseModel):
    """오류 내용."""

    code: str
    message: str
    details: list[FieldErrorOut] | None = None


class ErrorResponse(BaseModel):
    """모든 오류 응답의 공통 형식."""

    error: ErrorDetail
