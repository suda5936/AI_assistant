"""T-02 인수 테스트: 공통 오류 응답 형식 (AC-3, AC-4의 오류 형식 기반).

기준: 설계 문서 "오류 처리" 표.
"""

import pytest
from board.main import create_app
from fastapi.testclient import TestClient
from pydantic import BaseModel


class _Body(BaseModel):
    username: str
    password: str


def _boom() -> None:
    raise RuntimeError("SECRET_INTERNAL_DETAIL /etc/passwd")


def _echo(body: _Body) -> dict:
    return {"ok": True}


@pytest.fixture
def client():
    app = create_app()
    app.add_api_route("/api/_qa/echo", _echo, methods=["POST"])
    app.add_api_route("/api/_qa/boom", _boom, methods=["GET", "POST"])
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _assert_error(resp, status, code, message=None):
    assert resp.status_code == status, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert set(body) == {"error"}
    err = body["error"]
    assert err["code"] == code
    assert isinstance(err["message"], str) and err["message"]
    if message is not None:
        assert err["message"] == message
    return err


J = {"Content-Type": "application/json"}


def test_ac3_ac4_422_missing_fields_has_details(client):
    r = client.post("/api/_qa/echo", content="{}", headers=J)
    err = _assert_error(r, 422, "validation_error", "입력값을 확인해 주세요.")
    fields = {d["field"] for d in err["details"]}
    assert fields == {"username", "password"}
    assert all(d["message"] == "형식이 올바르지 않습니다." for d in err["details"])


def test_ac3_ac4_422_wrong_type(client):
    r = client.post("/api/_qa/echo", content='{"username": 123, "password": ["x"]}', headers=J)
    err = _assert_error(r, 422, "validation_error")
    assert {d["field"] for d in err["details"]} == {"username", "password"}


@pytest.mark.parametrize("content", ["{not json", ""])
def test_ac3_ac4_422_malformed_json_and_empty_body(client, content):
    r = client.post("/api/_qa/echo", content=content, headers=J)
    _assert_error(r, 422, "validation_error")


def test_ac3_ac4_422_valid_body_passes(client):
    r = client.post("/api/_qa/echo", json={"username": "a", "password": "b"})
    assert r.status_code == 200


def test_404_unknown_path_json_format(client):
    err = _assert_error(
        client.get("/api/does-not-exist"), 404, "not_found", "요청한 경로를 찾을 수 없습니다."
    )
    assert "details" not in err


def test_404_repeated_same_result(client):
    assert client.get("/api/nope").json() == client.get("/api/nope").json()


def test_405_method_not_allowed_format(client):
    r = client.get("/api/_qa/echo")
    _assert_error(r, 405, "method_not_allowed", "허용되지 않은 요청 방식입니다.")


def test_405_delete_on_post_route(client):
    r = client.delete("/api/_qa/echo", headers=J)
    _assert_error(r, 405, "method_not_allowed")


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "ctype", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"]
)
def test_415_non_json_state_changing(client, method, ctype):
    r = client.request(method, "/api/_qa/echo", content="a=b", headers={"Content-Type": ctype})
    _assert_error(r, 415, "unsupported_media_type", "JSON 형식으로 요청해 주세요.")


def test_415_missing_content_type(client):
    r = client.post("/api/_qa/echo", content=b"{}")
    _assert_error(r, 415, "unsupported_media_type")


def test_415_not_applied_to_get(client):
    r = client.get("/api/_qa/boom")
    assert r.status_code == 500


@pytest.mark.parametrize(
    "ctype", ["application/json", "application/json; charset=utf-8", "Application/JSON"]
)
def test_415_json_media_type_variants_accepted(client, ctype):
    r = client.post(
        "/api/_qa/echo",
        content='{"username":"a","password":"b"}',
        headers={"Content-Type": ctype},
    )
    assert r.status_code == 200


def test_415_lookalike_media_type_rejected(client):
    r = client.post(
        "/api/_qa/echo",
        content='{"username":"a","password":"b"}',
        headers={"Content-Type": "application/jsonx"},
    )
    _assert_error(r, 415, "unsupported_media_type")


def test_500_unexpected_exception_hides_internals(client):
    r = client.get("/api/_qa/boom")
    err = _assert_error(r, 500, "internal_error", "일시적인 오류가 발생했습니다.")
    for leak in ["SECRET_INTERNAL_DETAIL", "RuntimeError", "Traceback", "passwd", 'File "', ".py"]:
        assert leak not in r.text
    assert "details" not in err


def test_500_post_with_json_also_json_error(client):
    r = client.post("/api/_qa/boom", content="{}", headers=J)
    _assert_error(r, 500, "internal_error")
    assert "SECRET_INTERNAL_DETAIL" not in r.text


def test_500_server_keeps_working_afterwards(client):
    client.get("/api/_qa/boom")
    client.get("/api/_qa/boom")
    assert client.post("/api/_qa/echo", json={"username": "a", "password": "b"}).status_code == 200
