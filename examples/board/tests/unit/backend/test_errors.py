"""공통 오류 처리(errors.py, api/middleware.py) 단위 테스트."""

import logging

import pytest
from board.errors import (
    FieldError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    UsernameTakenError,
    ValidationFailedError,
    error_body,
    field_from_loc,
    register_exception_handlers,
)
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class _Payload(BaseModel):
    name: str


@pytest.fixture
def error_client(app: FastAPI) -> TestClient:
    """오류를 일으키는 테스트용 경로가 붙은 클라이언트(서버 예외를 응답으로 받는다)."""

    @app.get("/api/_t/validation")
    def raise_validation() -> None:
        raise ValidationFailedError(
            [FieldError("username", "나쁨"), FieldError("password", "짧음")]
        )

    @app.get("/api/_t/taken")
    def raise_taken() -> None:
        raise UsernameTakenError()

    @app.get("/api/_t/credentials")
    def raise_credentials() -> None:
        raise InvalidCredentialsError()

    @app.get("/api/_t/unauth")
    def raise_unauth() -> None:
        raise NotAuthenticatedError()

    @app.get("/api/_t/teapot")
    def raise_teapot() -> None:
        raise StarletteHTTPException(status_code=418)

    @app.get("/api/_t/boom")
    def raise_boom() -> None:
        raise RuntimeError("secret-internal-detail")

    @app.post("/api/_t/echo")
    def echo(body: _Payload) -> dict[str, str]:
        return {"name": body.name}

    @app.get("/other/_t/post-ok")
    def other_get() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/other/_t/post-ok")
    def other_post() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_error_body_without_details() -> None:
    assert error_body("c", "m") == {"error": {"code": "c", "message": "m"}}


def test_error_body_with_details() -> None:
    body = error_body("c", "m", [FieldError("f", "x")])
    assert body == {
        "error": {"code": "c", "message": "m", "details": [{"field": "f", "message": "x"}]}
    }


def test_error_body_with_empty_details_keeps_key() -> None:
    assert error_body("c", "m", [])["error"]["details"] == []


def test_validation_failed_response(error_client: TestClient) -> None:
    response = error_client.get("/api/_t/validation")
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "입력값을 확인해 주세요.",
            "details": [
                {"field": "username", "message": "나쁨"},
                {"field": "password", "message": "짧음"},
            ],
        }
    }


@pytest.mark.parametrize(
    ("path", "status", "code", "message"),
    [
        ("taken", 409, "username_taken", "이미 사용 중인 아이디입니다."),
        ("credentials", 401, "invalid_credentials", "아이디 또는 비밀번호가 올바르지 않습니다."),
        ("unauth", 401, "unauthenticated", "로그인이 필요합니다."),
    ],
)
def test_app_errors(
    error_client: TestClient, path: str, status: int, code: str, message: str
) -> None:
    response = error_client.get(f"/api/_t/{path}")
    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "message": message}}


def test_request_validation_missing_field(error_client: TestClient) -> None:
    response = error_client.post("/api/_t/echo", json={})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "입력값을 확인해 주세요.",
            "details": [{"field": "name", "message": "형식이 올바르지 않습니다."}],
        }
    }


def test_request_validation_wrong_type(error_client: TestClient) -> None:
    response = error_client.post("/api/_t/echo", json={"name": ["a"]})
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "name"


def test_request_validation_invalid_json_body(error_client: TestClient) -> None:
    response = error_client.post(
        "/api/_t/echo", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "입력값을 확인해 주세요."
    assert len(error["details"]) == 1
    assert error["details"][0]["message"] == "형식이 올바르지 않습니다."
    assert error["details"][0]["field"] == "body"


@pytest.mark.parametrize(
    ("loc", "expected"),
    [
        (("body", "username"), "username"),
        (("body", 1), "body"),
        (("body",), "body"),
        (("body", "tags", 0), "tags"),
        (("query", "page"), "page"),
        ((), "body"),
        (None, "body"),
        ((0, 1), "body"),
    ],
)
def test_field_from_loc(loc: tuple[str | int, ...] | None, expected: str) -> None:
    assert field_from_loc(loc) == expected


def test_request_validation_top_level_array_body(error_client: TestClient) -> None:
    response = error_client.post("/api/_t/echo", json=[1, 2])
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body"


def test_request_validation_error_without_loc_uses_body_field() -> None:
    exc = RequestValidationError([{"type": "x", "msg": "m", "input": None}])
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise exc

    response = TestClient(app).get("/boom")
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "body", "message": "형식이 올바르지 않습니다."}
    ]


def test_not_found(error_client: TestClient) -> None:
    response = error_client.get("/api/nothing")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "요청한 경로를 찾을 수 없습니다."}
    }


def test_method_not_allowed(error_client: TestClient) -> None:
    response = error_client.put("/other/_t/post-ok", json={})
    assert response.status_code == 405
    assert response.json() == {
        "error": {"code": "method_not_allowed", "message": "허용되지 않은 요청 방식입니다."}
    }


def test_other_http_exception(error_client: TestClient) -> None:
    response = error_client.get("/api/_t/teapot")
    assert response.status_code == 418
    assert response.json() == {
        "error": {"code": "http_error", "message": "요청을 처리할 수 없습니다."}
    }


def test_unexpected_exception_hides_internal_info(
    error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="board.errors"):
        response = error_client.get("/api/_t/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "일시적인 오류가 발생했습니다."}
    }
    assert "secret-internal-detail" not in response.text
    assert "Traceback" not in response.text
    assert "secret-internal-detail" in caplog.text


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_non_json_state_change_returns_415(error_client: TestClient, method: str) -> None:
    response = error_client.request(
        method.upper(), "/api/_t/echo", content="x", headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 415
    assert response.json() == {
        "error": {"code": "unsupported_media_type", "message": "JSON 형식으로 요청해 주세요."}
    }


def test_missing_content_type_returns_415(error_client: TestClient) -> None:
    response = error_client.post("/api/_t/echo")
    assert response.status_code == 415


def test_json_with_charset_and_uppercase_passes(error_client: TestClient) -> None:
    response = error_client.post(
        "/api/_t/echo",
        content='{"name": "a"}',
        headers={"Content-Type": "Application/JSON; charset=utf-8"},
    )
    assert response.status_code == 200
    assert response.json() == {"name": "a"}


def test_get_is_not_checked(error_client: TestClient) -> None:
    assert error_client.get("/api/_t/unauth").status_code == 401


def test_non_api_path_is_not_checked(error_client: TestClient) -> None:
    response = error_client.post(
        "/other/_t/post-ok", content="x", headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 200
