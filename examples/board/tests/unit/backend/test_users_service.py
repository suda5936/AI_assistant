"""services/users.py::create_user 단위 테스트."""

from datetime import datetime

import pytest
from board.errors import InvalidCredentialsError, UsernameTakenError, ValidationFailedError
from board.models import User
from board.services import users as users_service
from board.services.users import authenticate, create_user
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

NOW = datetime(2026, 1, 2, 3, 4, 5)


def _count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def test_create_user_stores_lowercase_username_and_hash(db: Session) -> None:
    user = create_user(db, "AliceKim", "password1", NOW)
    db.expire_all()
    row = db.execute(
        text("select username, password_hash, created_at from users where id = :id"),
        {"id": user.id},
    ).one()
    assert row.username == "alicekim"
    assert str(row.created_at).startswith("2026-01-02 03:04:05")
    assert row.password_hash != "password1"
    assert row.password_hash.startswith("scrypt$")
    assert "password1" not in row.password_hash


def test_same_password_different_hashes(db: Session) -> None:
    first = create_user(db, "userone", "password1", NOW)
    second = create_user(db, "usertwo", "password1", NOW)
    db.expire_all()
    hashes = db.scalars(select(User.password_hash)).all()
    assert len(set(hashes)) == 2
    assert first.password_hash != second.password_hash


def test_duplicate_username_rejected(db: Session) -> None:
    create_user(db, "alice", "password1", NOW)
    with pytest.raises(UsernameTakenError):
        create_user(db, "alice", "password2", NOW)
    assert _count(db) == 1


def test_case_insensitive_duplicate_rejected(db: Session) -> None:
    create_user(db, "alice", "password1", NOW)
    with pytest.raises(UsernameTakenError):
        create_user(db, "ALICE", "password1", NOW)
    assert _count(db) == 1


def test_invalid_input_not_saved(db: Session) -> None:
    with pytest.raises(ValidationFailedError):
        create_user(db, "ab", "short", NOW)
    with pytest.raises(ValidationFailedError):
        create_user(db, "alice", "a\ud800bcdefgh", NOW)
    assert _count(db) == 0


def test_integrity_error_becomes_username_taken(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_commit() -> None:
        raise IntegrityError("insert", {}, Exception("unique"))

    monkeypatch.setattr(db, "commit", fail_commit)
    rolled_back: list[bool] = []
    monkeypatch.setattr(db, "rollback", lambda: rolled_back.append(True))
    with pytest.raises(UsernameTakenError):
        users_service.create_user(db, "alice", "password1", NOW)
    assert rolled_back == [True]


def test_authenticate_success_is_case_insensitive(db: Session) -> None:
    created = create_user(db, "alice", "password1", NOW)
    assert authenticate(db, "ALICE", "password1").id == created.id


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("alice", "wrong-password"),
        ("nobody", "password1"),
        ("alice", "a" * 73),
        ("alice", "a\ud800bcdefgh"),
        ("nobody", "a\ud800bcdefgh"),
        ("a\ud800bc", "password1"),
        ("", ""),
    ],
)
def test_authenticate_failures_raise_same_error(db: Session, username: str, password: str) -> None:
    create_user(db, "alice", "password1", NOW)
    with pytest.raises(InvalidCredentialsError) as info:
        authenticate(db, username, password)
    assert info.value.code == "invalid_credentials"
    assert info.value.message == "아이디 또는 비밀번호가 올바르지 않습니다."


def test_authenticate_unknown_user_runs_dummy_verify(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(users_service, "verify_dummy", calls.append)
    with pytest.raises(InvalidCredentialsError):
        authenticate(db, "nobody", "password1")
    assert calls == ["password1"]


@pytest.mark.parametrize("password", ["a" * 73, "a\ud800bcdefgh", "wrong-password"])
def test_authenticate_scrypt_cost_same_for_known_and_unknown_user(
    db: Session, monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    create_user(db, "alice", "password1", NOW)
    patterns: dict[str, list[str]] = {}
    current: list[str] = []
    monkeypatch.setattr(users_service, "verify_dummy", lambda _pw: current.append("scrypt"))
    monkeypatch.setattr(
        users_service, "verify_password", lambda _pw, _hash: current.append("scrypt") or False
    )
    for username in ("alice", "nobody"):
        current.clear()
        with pytest.raises(InvalidCredentialsError):
            authenticate(db, username, password)
        patterns[username] = list(current)
    assert patterns["alice"] == patterns["nobody"]
    if len(password) > 72:
        assert patterns["alice"] == []
    else:
        assert patterns["alice"] == ["scrypt"]
