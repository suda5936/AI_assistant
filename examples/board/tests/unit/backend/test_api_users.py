"""POST /api/users 단위 테스트."""

import json

import pytest
from board.models import User
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

USERNAME_FORMAT = "아이디는 영문 소문자, 숫자, 밑줄(_)로 4~20자여야 합니다."


def _count(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(User)) or 0


def test_signup_success(client: TestClient, db: Session) -> None:
    response = client.post("/api/users", json={"username": "AliceKim", "password": "password1"})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "username", "created_at"}
    assert body["username"] == "alicekim"
    assert body["created_at"].endswith("Z")
    assert "password" not in response.text
    assert "scrypt" not in response.text
    assert _count(db) == 1


def test_signup_duplicate_is_409(client: TestClient, db: Session) -> None:
    client.post("/api/users", json={"username": "alice", "password": "password1"})
    response = client.post("/api/users", json={"username": "ALICE", "password": "password2"})
    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "username_taken", "message": "이미 사용 중인 아이디입니다."}
    }
    assert _count(db) == 1


def test_signup_validation_details(client: TestClient, db: Session) -> None:
    response = client.post("/api/users", json={"username": "ab", "password": "short"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "입력값을 확인해 주세요.",
            "details": [
                {"field": "username", "message": USERNAME_FORMAT},
                {"field": "password", "message": "비밀번호는 8자 이상이어야 합니다."},
            ],
        }
    }
    assert _count(db) == 0


@pytest.mark.parametrize(("length", "status"), [(7, 422), (8, 201), (72, 201), (73, 422)])
def test_signup_password_boundaries(client: TestClient, length: int, status: int) -> None:
    response = client.post("/api/users", json={"username": "alice", "password": "a" * length})
    assert response.status_code == status


def test_signup_unencodable_password_is_422(client: TestClient, db: Session) -> None:
    content = '{"username": "alice", "password": "a\\ud800bcdefgh"}'
    response = client.post(
        "/api/users", content=content, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "password", "message": "비밀번호에 사용할 수 없는 문자가 포함되어 있습니다."}
    ]
    assert _count(db) == 0


@pytest.mark.parametrize(
    ("payload", "fields"),
    [
        ({}, ["username", "password"]),
        ({"username": "alice"}, ["password"]),
        ({"username": 1, "password": "password1"}, ["username"]),
    ],
)
def test_signup_missing_or_wrong_type_fields(
    client: TestClient, payload: dict[str, object], fields: list[str]
) -> None:
    response = client.post("/api/users", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert [item["field"] for item in error["details"]] == fields


def test_signup_requires_json_content_type(client: TestClient) -> None:
    response = client.post(
        "/api/users",
        content=json.dumps({"username": "alice", "password": "password1"}),
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_openapi_documents_415_for_signup(client: TestClient) -> None:
    schema = client.app.openapi()
    assert set(schema["paths"]["/api/users"]["post"]["responses"]) >= {"201", "409", "415", "422"}
