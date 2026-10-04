"""로그인·로그아웃·me API 단위 테스트."""

import json
from datetime import timedelta

import httpx
import pytest
from board.config import SESSION_COOKIE_NAME, Settings
from board.db import Base, create_db_engine
from board.main import create_app
from board.models import UserSession
from board.timeutil import utc_now
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

INVALID = {
    "error": {
        "code": "invalid_credentials",
        "message": "아이디 또는 비밀번호가 올바르지 않습니다.",
    }
}
VALID_INPUT = "password1"
UNAUTHENTICATED = {"error": {"code": "unauthenticated", "message": "로그인이 필요합니다."}}


def _signup(client: TestClient) -> None:
    response = client.post("/api/users", json={"username": "alice", "password": VALID_INPUT})
    assert response.status_code == 201


def _login(client: TestClient, username: str = "alice") -> httpx.Response:
    return client.post("/api/auth/login", json={"username": username, "password": VALID_INPUT})


def _session_count(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(UserSession)) or 0


def test_login_sets_cookie_and_me_works(client: TestClient) -> None:
    _signup(client)
    response = _login(client, "ALICE")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "username", "created_at"}
    assert body["username"] == "alice"
    assert "password" not in response.text
    assert "scrypt" not in response.text
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == body


def test_login_cookie_attributes(client: TestClient) -> None:
    _signup(client)
    cookie = _login(client).headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "samesite=lax" in lowered
    assert "path=/" in lowered
    assert "max-age=604800" in lowered
    assert "secure" not in lowered


def test_login_cookie_secure_when_configured(tmp_path_factory: pytest.TempPathFactory) -> None:
    path = tmp_path_factory.mktemp("secure")
    settings = Settings(database_url=f"sqlite:///{path}/t.db", session_cookie_secure=True)
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    with TestClient(create_app(settings)) as secure_client:
        _signup(secure_client)
        cookie = _login(secure_client).headers["set-cookie"]
    assert "secure" in cookie.lower()


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("alice", "wrong-password"),
        ("nobody", "password1"),
        ("alice", "a\ud800bcdefgh"),
        ("nobody", "a\ud800bcdefgh"),
        ("a\ud800bc", "password1"),
        ("a!", "password1"),
        ("", ""),
        ("alice", "a" * 100),
    ],
)
def test_login_failures_are_identical(client: TestClient, username: str, password: str) -> None:
    _signup(client)
    content = json.dumps({"username": username, "password": password})
    response = client.post(
        "/api/auth/login", content=content, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 401
    assert response.json() == INVALID
    assert "set-cookie" not in response.headers


def test_login_missing_fields_is_422(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "alice"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert [item["field"] for item in error["details"]] == ["password"]


def test_login_requires_json_content_type(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", content="username=a", headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 415


def test_me_without_cookie_is_401(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == UNAUTHENTICATED


@pytest.mark.parametrize("cookie_value", ["unknown-token", ""])
def test_me_with_bad_cookie_is_401(client: TestClient, cookie_value: str) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, cookie_value)
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == UNAUTHENTICATED


def test_me_with_expired_session_is_401(client: TestClient, db: Session) -> None:
    _signup(client)
    _login(client)
    db.execute(update(UserSession).values(expires_at=utc_now() - timedelta(seconds=1)))
    db.commit()
    assert client.get("/api/auth/me").status_code == 401
    assert _session_count(db) == 0


def test_logout_invalidates_old_token(client: TestClient, db: Session) -> None:
    _signup(client)
    token = _login(client).cookies[SESSION_COOKIE_NAME]
    response = client.post("/api/auth/logout", json={})
    assert response.status_code == 204
    assert response.content == b""
    cleared = response.headers["set-cookie"].lower()
    assert "max-age=0" in cleared
    assert "path=/" in cleared
    assert "httponly" in cleared
    assert "samesite=lax" in cleared
    assert _session_count(db) == 0
    client.cookies.set(SESSION_COOKIE_NAME, token)
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_cookie_is_204(client: TestClient) -> None:
    assert client.post("/api/auth/logout", json={}).status_code == 204


def test_logout_requires_json_content_type(client: TestClient) -> None:
    response = client.post("/api/auth/logout", content="", headers={"Content-Type": "text/plain"})
    assert response.status_code == 415


def test_openapi_documents_auth_errors(client: TestClient) -> None:
    paths = client.app.openapi()["paths"]
    assert set(paths["/api/auth/login"]["post"]["responses"]) >= {"200", "401", "415", "422"}
    assert set(paths["/api/auth/logout"]["post"]["responses"]) >= {"204", "415"}
    assert set(paths["/api/auth/me"]["get"]["responses"]) >= {"200", "401"}
