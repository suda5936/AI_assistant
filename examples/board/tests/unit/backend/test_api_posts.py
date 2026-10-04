"""게시글 API 단위 테스트 (정상, 검증, 401, 403, 404)."""

from collections.abc import Callable

import pytest
from board.main import create_app
from board.models import User
from fastapi.testclient import TestClient

LoginClient = Callable[[str], TestClient]
MakeUser = Callable[[str], User]
VALID = {"title": "제목", "content": "내용\n둘째 줄"}


def _total(client: TestClient) -> int:
    return client.get("/api/posts").json()["total"]


def _create(client: TestClient, title: str = "제목", content: str = "내용") -> dict:
    response = client.post("/api/posts", json={"title": title, "content": content})
    assert response.status_code == 201
    return response.json()


def test_list_empty_without_cookie(client: TestClient) -> None:
    response = client.get("/api/posts")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "size": 10}


@pytest.mark.parametrize("raw", ["0", "-1", "abc", "999", "99999999999999999999", "1e3", ""])
def test_list_page_is_corrected_to_200(
    client: TestClient, make_user: MakeUser, login_client: LoginClient, raw: str
) -> None:
    make_user("alice")
    writer = login_client("alice")
    for index in range(11):
        _create(writer, f"t{index}")
    response = client.get("/api/posts", params={"page": raw})
    assert response.status_code == 200
    expected_page = 2 if raw in {"999", "99999999999999999999"} else 1
    assert response.json()["page"] == expected_page


def test_list_leading_zero_page_and_order(
    client: TestClient, make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    writer = login_client("alice")
    for index in range(11):
        _create(writer, f"t{index}")
    body = client.get("/api/posts?page=0000000002").json()
    assert body["page"] == 2
    assert [item["title"] for item in body["items"]] == ["t0"]
    first = client.get("/api/posts").json()
    assert len(first["items"]) == 10
    assert first["items"][0]["title"] == "t10"
    assert set(first["items"][0]) == {"id", "title", "author", "created_at"}


def test_create_and_get(client: TestClient, make_user: MakeUser, login_client: LoginClient) -> None:
    make_user("alice")
    writer = login_client("alice")
    created = writer.post("/api/posts", json=VALID)
    assert created.status_code == 201
    body = created.json()
    assert body["content"] == VALID["content"]
    assert body["author"] == {"id": 1, "username": "alice"}
    assert body["created_at"].endswith("Z")
    assert client.get(f"/api/posts/{body['id']}").json() == body


def test_create_requires_login(client: TestClient) -> None:
    response = client.post("/api/posts", json=VALID)
    assert (response.status_code, response.json()["error"]["code"]) == (401, "unauthenticated")
    assert _total(client) == 0


def test_create_with_logged_out_cookie_is_401(
    client: TestClient, make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    writer = login_client("alice")
    writer.post("/api/auth/logout", json={})
    assert writer.post("/api/posts", json=VALID).status_code == 401
    assert _total(client) == 0


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({"title": "  ", "content": "c"}, "title", "제목을 입력해 주세요."),
        ({"title": "a" * 101, "content": "c"}, "title", "제목은 100자 이하여야 합니다."),
        ({"title": "t", "content": "\n\t"}, "content", "내용을 입력해 주세요."),
        ({"title": "t", "content": "a" * 5001}, "content", "내용은 5000자 이하여야 합니다."),
    ],
)
def test_create_validation_errors(
    client: TestClient,
    make_user: MakeUser,
    login_client: LoginClient,
    payload: dict,
    field: str,
    message: str,
) -> None:
    make_user("alice")
    writer = login_client("alice")
    response = writer.post("/api/posts", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"] == [{"field": field, "message": message}]
    assert _total(client) == 0


def test_create_missing_field_is_422(make_user: MakeUser, login_client: LoginClient) -> None:
    make_user("alice")
    response = login_client("alice").post("/api/posts", json={"title": "t"})
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "content"


def test_create_boundaries_and_emoji(make_user: MakeUser, login_client: LoginClient) -> None:
    make_user("alice")
    writer = login_client("alice")
    assert writer.post("/api/posts", json={"title": "a" * 100, "content": "c"}).status_code == 201
    emoji = "\U0001f600" * 5000
    assert writer.post("/api/posts", json={"title": "t", "content": emoji}).status_code == 201


def test_text_is_stored_verbatim(make_user: MakeUser, login_client: LoginClient) -> None:
    make_user("alice")
    writer = login_client("alice")
    script = "<script>alert(1)</script>"
    created = _create(writer, script, script)
    assert (created["title"], created["content"]) == (script, script)


@pytest.mark.parametrize("raw", ["999999", "abc", "0", "-1", "01", "9" * 30])
def test_get_unknown_id_is_404(client: TestClient, raw: str) -> None:
    response = client.get(f"/api/posts/{raw}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "post_not_found"


def test_update_by_author(
    client: TestClient, make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    writer = login_client("alice")
    created = _create(writer)
    response = writer.put(
        f"/api/posts/{created['id']}", json={"title": "새 제목", "content": "새 내용"}
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["content"]) == ("새 제목", "새 내용")
    assert body["created_at"] == created["created_at"]
    assert body["author"] == created["author"]
    assert client.get(f"/api/posts/{created['id']}").json() == body
    assert client.get("/api/posts").json()["items"][0]["title"] == "새 제목"


@pytest.mark.parametrize("title", ["", "a" * 101])
def test_update_validation_error(
    make_user: MakeUser, login_client: LoginClient, title: str
) -> None:
    make_user("alice")
    writer = login_client("alice")
    created = _create(writer)
    response = writer.put(f"/api/posts/{created['id']}", json={"title": title, "content": "c"})
    assert response.status_code == 422
    assert writer.get(f"/api/posts/{created['id']}").json() == created


def test_update_and_delete_by_other_user_is_403(
    client: TestClient, make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    make_user("bobby")
    created = _create(login_client("alice"))
    other = login_client("bobby")
    url = f"/api/posts/{created['id']}"
    put = other.put(url, json={"title": "x", "content": "y"})
    assert (put.status_code, put.json()["error"]["code"]) == (403, "forbidden")
    assert other.put(url, json={"title": "", "content": ""}).status_code == 403
    delete = other.request("DELETE", url, json={})
    assert (delete.status_code, delete.json()["error"]["code"]) == (403, "forbidden")
    assert client.get(url).json() == created


def test_update_and_delete_without_login_is_401(
    client: TestClient, login_client: LoginClient, make_user: MakeUser
) -> None:
    make_user("alice")
    created = _create(login_client("alice"))
    url = f"/api/posts/{created['id']}"
    assert client.put(url, json=VALID).status_code == 401
    assert client.request("DELETE", url, json={}).status_code == 401
    assert client.get(url).json() == created


def test_update_and_delete_missing_post_is_404(
    make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    writer = login_client("alice")
    assert writer.put("/api/posts/999", json=VALID).status_code == 404
    assert writer.request("DELETE", "/api/posts/999", json={}).status_code == 404
    assert writer.put("/api/posts/abc", json=VALID).status_code == 404
    assert writer.request("DELETE", "/api/posts/" + "9" * 30, json={}).status_code == 404


def test_delete_by_author(
    client: TestClient, make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    writer = login_client("alice")
    created = _create(writer)
    response = writer.request("DELETE", f"/api/posts/{created['id']}", json={})
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/posts/{created['id']}").status_code == 404
    assert _total(client) == 0


def test_delete_requires_json_content_type(make_user: MakeUser, login_client: LoginClient) -> None:
    make_user("alice")
    writer = login_client("alice")
    created = _create(writer)
    response = writer.delete(f"/api/posts/{created['id']}", headers={"Content-Type": "text/plain"})
    assert response.status_code == 415


def test_create_unencodable_character_is_422(
    client: TestClient, make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    writer = login_client("alice")
    response = writer.post(
        "/api/posts",
        content=b'{"title": "\\ud800", "content": "c"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "title", "message": "제목에 사용할 수 없는 문자가 포함되어 있습니다."}
    ]
    assert _total(client) == 0


def test_update_validation_runs_before_404_and_403(
    make_user: MakeUser, login_client: LoginClient
) -> None:
    make_user("alice")
    make_user("bobby")
    created = _create(login_client("alice"))
    other = login_client("bobby")
    missing = other.put("/api/posts/999", json={"title": "t"})
    assert missing.status_code == 422
    wrong_type = other.put(f"/api/posts/{created['id']}", json={"title": 1, "content": "c"})
    assert wrong_type.status_code == 422
    assert wrong_type.json()["error"]["code"] == "validation_error"


def test_openapi_declares_422_as_error_response() -> None:
    paths = create_app().openapi()["paths"]
    expected = "#/components/schemas/ErrorResponse"
    for path, method in [
        ("/api/posts", "get"),
        ("/api/posts", "post"),
        ("/api/posts/{post_id}", "get"),
        ("/api/posts/{post_id}", "put"),
        ("/api/posts/{post_id}", "delete"),
    ]:
        schema = paths[path][method]["responses"]["422"]["content"]["application/json"]["schema"]
        assert schema == {"$ref": expected}, (path, method)
