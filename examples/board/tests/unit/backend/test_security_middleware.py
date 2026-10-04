"""요청 보호 단위 테스트 (본문 상한, 보안 헤더, 문서 경로, CORS)."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from board import openapi_export
from board.config import MAX_REQUEST_BODY_BYTES, Settings
from board.main import create_app
from board.models import User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

JSON_HEADERS = {"Content-Type": "application/json"}
SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
}


def _body_of_size(size: int) -> bytes:
    """JSON 객체이면서 정확히 size 바이트인 본문을 만든다."""
    prefix = b'{"title":"t","content":"'
    suffix = b'"}'
    return prefix + b"x" * (size - len(prefix) - len(suffix)) + suffix


def _chunks() -> Iterator[bytes]:
    yield b'{"title":"t",'
    yield b'"content":"c"}'


def _assert_security_headers(response_headers: dict[str, str]) -> None:
    for name, value in SECURITY_HEADERS.items():
        assert response_headers.get(name) == value


def test_max_request_body_bytes_is_64_kib() -> None:
    assert MAX_REQUEST_BODY_BYTES == 65536


def test_body_over_limit_is_413(
    client: TestClient, make_user: Callable[[str], User], login_client: Callable[[str], TestClient]
) -> None:
    make_user("alice")
    writer = login_client("alice")
    response = writer.post(
        "/api/posts", content=_body_of_size(MAX_REQUEST_BODY_BYTES + 1), headers=JSON_HEADERS
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert writer.get("/api/posts").json()["total"] == 0


def test_body_at_limit_is_processed(
    make_user: Callable[[str], User], login_client: Callable[[str], TestClient]
) -> None:
    make_user("alice")
    writer = login_client("alice")
    response = writer.post(
        "/api/posts", content=_body_of_size(MAX_REQUEST_BODY_BYTES), headers=JSON_HEADERS
    )
    # 크기 검사는 통과하고 내용 길이 검증(422)이 처리한다.
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_normal_body_is_created(
    make_user: Callable[[str], User], login_client: Callable[[str], TestClient]
) -> None:
    make_user("alice")
    response = login_client("alice").post("/api/posts", json={"title": "t", "content": "c"})
    assert response.status_code == 201


def test_chunked_body_is_411(client: TestClient) -> None:
    response = client.post("/api/posts", content=_chunks(), headers=JSON_HEADERS)
    assert response.status_code == 411
    assert response.json()["error"]["code"] == "length_required"


@pytest.mark.parametrize("raw", ["abc", "-1", "1.5", ""])
def test_non_numeric_content_length_is_411(client: TestClient, raw: str) -> None:
    response = client.post(
        "/api/posts", content=b"{}", headers={**JSON_HEADERS, "Content-Length": raw}
    )
    assert response.status_code == 411
    assert response.json()["error"]["code"] == "length_required"


def test_non_json_with_large_body_is_415_first(client: TestClient) -> None:
    response = client.post(
        "/api/posts",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415


def test_non_json_chunked_is_415_first(client: TestClient) -> None:
    response = client.post("/api/posts", content=_chunks(), headers={"Content-Type": "text/plain"})
    assert response.status_code == 415


def test_get_with_large_content_length_is_not_limited(client: TestClient) -> None:
    response = client.get("/api/posts", headers={"Content-Length": "999999"})
    assert response.status_code != 413


def test_non_api_path_is_not_limited(client: TestClient) -> None:
    response = client.post(
        "/other", content=b"x" * (MAX_REQUEST_BODY_BYTES + 1), headers=JSON_HEADERS
    )
    assert response.status_code == 404


def test_security_headers_on_get(client: TestClient) -> None:
    _assert_security_headers(dict(client.get("/api/posts").headers))


def test_security_headers_on_post(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "a", "password": "b"})
    assert response.status_code == 401
    _assert_security_headers(dict(response.headers))


def test_security_headers_on_415_411_413_404(client: TestClient) -> None:
    responses = [
        client.post("/api/posts", content=b"{}", headers={"Content-Type": "text/plain"}),
        client.post("/api/posts", content=_chunks(), headers=JSON_HEADERS),
        client.post(
            "/api/posts",
            content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
            headers=JSON_HEADERS,
        ),
        client.get("/nothing"),
    ]
    assert [r.status_code for r in responses] == [415, 411, 413, 404]
    for response in responses:
        _assert_security_headers(dict(response.headers))


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_paths_are_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_openapi_export_still_works(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "openapi.json"
    assert openapi_export.main([str(target)]) == 0
    assert "/api/posts" in json.loads(target.read_text(encoding="utf-8"))["paths"]


def test_no_cors_headers(client: TestClient) -> None:
    origin = {"Origin": "https://evil.example"}
    preflight = client.options(
        "/api/posts", headers={**origin, "Access-Control-Request-Method": "POST"}
    )
    cross_post = client.post("/api/posts", json={"title": "t", "content": "c"}, headers=origin)
    for response in (preflight, cross_post):
        assert not any(name.lower().startswith("access-control-") for name in response.headers)


VALID_POST_JSON = b'{"title":"t","content":"c"}'
SIGNUP_JSON = b'{"username":"alice1","password":"password1"}'


def test_content_length_with_transfer_encoding_is_411(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/users",
        content=SIGNUP_JSON,
        headers={**JSON_HEADERS, "Content-Length": "10", "Transfer-Encoding": "chunked"},
    )
    assert response.status_code == 411
    assert response.json()["error"]["code"] == "length_required"
    assert db.query(User).count() == 0


def test_non_chunked_transfer_encoding_is_411(client: TestClient) -> None:
    response = client.post(
        "/api/users",
        content=SIGNUP_JSON,
        headers={**JSON_HEADERS, "Content-Length": "10", "Transfer-Encoding": "identity"},
    )
    assert response.status_code == 411


def test_duplicate_content_length_is_411(client: TestClient) -> None:
    response = client.post(
        "/api/posts",
        content=b"0123456789",
        headers=[
            ("content-type", "application/json"),
            ("content-length", "10"),
            ("content-length", "10"),
        ],
    )
    assert response.status_code == 411
    assert response.json()["error"]["code"] == "length_required"


def test_huge_content_length_is_413_not_500(client: TestClient) -> None:
    response = client.post(
        "/api/posts",
        content=b"{}",
        headers={**JSON_HEADERS, "Content-Length": "9" * 5000},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_leading_zero_content_length_is_judged_by_value(client: TestClient) -> None:
    response = client.post(
        "/api/posts",
        content=VALID_POST_JSON,
        headers={**JSON_HEADERS, "Content-Length": "0" * 5000 + str(len(VALID_POST_JSON))},
    )
    # 크기 검사 통과, 본문이 올바르므로 비로그인 401. int(원문) 회귀면 500.
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_unexpected_exception_500_has_security_headers(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    _assert_security_headers(dict(response.headers))
