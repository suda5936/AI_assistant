"""services/sessions.py 단위 테스트."""

import re
from datetime import datetime, timedelta

from board.models import User, UserSession
from board.services.sessions import (
    create_session,
    delete_session,
    get_user_by_token,
    hash_token,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

NOW = datetime(2026, 1, 2, 3, 4, 5)
TTL = timedelta(days=7)


def _make_user(db: Session) -> User:
    user = User(username="alice", password_hash="x", created_at=NOW)
    db.add(user)
    db.commit()
    return user


def _count(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(UserSession)) or 0


def test_hash_token_is_sha256_hex() -> None:
    value = hash_token("abc")
    assert re.fullmatch(r"[0-9a-f]{64}", value)
    assert value == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_create_session_stores_only_hash(db: Session) -> None:
    user = _make_user(db)
    token = create_session(db, user, NOW, TTL)
    assert len(token) >= 43
    row = db.scalars(select(UserSession)).one()
    assert row.token_hash == hash_token(token)
    assert token not in row.token_hash
    assert row.user_id == user.id
    assert row.expires_at == NOW + TTL


def test_tokens_are_unique(db: Session) -> None:
    user = _make_user(db)
    assert create_session(db, user, NOW, TTL) != create_session(db, user, NOW, TTL)


def test_get_user_by_token_valid(db: Session) -> None:
    user = _make_user(db)
    token = create_session(db, user, NOW, TTL)
    found = get_user_by_token(db, token, NOW + timedelta(days=6))
    assert found is not None
    assert found.id == user.id


def test_get_user_by_token_unknown(db: Session) -> None:
    assert get_user_by_token(db, "unknown", NOW) is None


def test_get_user_by_token_expired_deletes_row(db: Session) -> None:
    user = _make_user(db)
    token = create_session(db, user, NOW, TTL)
    assert get_user_by_token(db, token, NOW + TTL) is None
    assert _count(db) == 0


def test_delete_session(db: Session) -> None:
    user = _make_user(db)
    token = create_session(db, user, NOW, TTL)
    delete_session(db, token)
    assert _count(db) == 0
    assert get_user_by_token(db, token, NOW) is None


def test_delete_session_unknown_is_noop(db: Session) -> None:
    user = _make_user(db)
    create_session(db, user, NOW, TTL)
    delete_session(db, "unknown")
    assert _count(db) == 1
