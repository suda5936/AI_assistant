"""T-03 인수 테스트: AC-5 비밀번호 해시 저장·검증 (명세·설계 문서 기준)."""

import base64
import hashlib
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from board.db import Base, create_db_engine, create_session_factory
from board.models import User, UserSession
from board.services.passwords import hash_password, verify_dummy, verify_password
from sqlalchemy.exc import IntegrityError

BACKEND = Path(__file__).resolve().parents[2] / "backend"
NOW = datetime(2026, 1, 1)


def test_ac5_hash_is_not_plaintext_and_has_scrypt_format():
    pw = "correct horse 1"
    h = hash_password(pw)
    assert pw not in h
    parts = h.split("$")
    assert parts[:4] == ["scrypt", "16384", "8", "1"]
    assert len(parts) == 6
    assert len(base64.b64decode(parts[4])) == 16
    assert len(base64.b64decode(parts[5])) == 64
    assert len(h) <= 255


def test_ac5_hash_matches_independent_scrypt_computation():
    pw = "abcdefgh"
    parts = hash_password(pw).split("$")
    salt = base64.b64decode(parts[4])
    expect = hashlib.scrypt(pw.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
    assert base64.b64decode(parts[5]) == expect


def test_ac5_same_password_gets_different_salted_hashes():
    assert hash_password("samepassword") != hash_password("samepassword")


def test_ac5_verify_success_and_failure():
    h = hash_password("password1")
    assert verify_password("password1", h) is True
    assert verify_password("password2", h) is False
    assert verify_password("Password1", h) is False
    assert verify_password("", h) is False
    assert verify_password("password1 ", h) is False


@pytest.mark.parametrize(
    "pw",
    ["12345678", "한글비밀번호입니다", "p" * 72, "a b\tc!@#$%^&*()", "😀" * 8],
)
def test_ac5_roundtrip_boundary_and_unicode(pw):
    assert verify_password(pw, hash_password(pw)) is True


@pytest.mark.parametrize(
    "broken",
    [
        "",
        "plaintext",
        "scrypt",
        "scrypt$16384$8$1",
        "scrypt$16384$8$1$$",
        "scrypt$x$8$1$AAAA$AAAA",
        "scrypt$16384$8$1$!!!notb64$!!!",
        "bcrypt$16384$8$1$AAAA$AAAA",
        "scrypt$0$0$0$AAAA$AAAA",
        "scrypt$16384$8$1$AAAA$AAAA$extra",
    ],
)
def test_ac5_broken_stored_hash_returns_false_without_exception(broken):
    assert verify_password("password1", broken) is False


def test_ac5_verify_dummy_returns_none_without_error():
    assert verify_dummy("whatever") is None
    assert verify_dummy("") is None


@pytest.fixture
def factory(tmp_path):
    path = tmp_path / "t.db"
    engine = create_db_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return create_session_factory(engine), path


def test_ac5_hash_stored_in_db_is_not_plaintext(factory):
    sf, path = factory
    pw = "plainsecret99"
    with sf() as s:
        s.add(User(username="alice", password_hash=hash_password(pw), created_at=NOW))
        s.commit()
    raw = sqlite3.connect(path).execute("select password_hash from users").fetchone()[0]
    assert raw != pw and pw not in raw and raw.startswith("scrypt$")
    assert verify_password(pw, raw)


def test_ac5_two_users_same_password_have_different_db_hashes(factory):
    sf, path = factory
    with sf() as s:
        for n in ("user_a", "user_b"):
            s.add(User(username=n, password_hash=hash_password("samepassword"), created_at=NOW))
        s.commit()
    rows = sqlite3.connect(path).execute("select password_hash from users").fetchall()
    assert len(rows) == 2 and rows[0][0] != rows[1][0]


def test_ac2_username_unique_constraint(factory):
    sf, _ = factory
    with sf() as s:
        s.add(User(username="dup_user", password_hash="x", created_at=NOW))
        s.commit()
    with sf() as s:
        s.add(User(username="dup_user", password_hash="y", created_at=NOW))
        with pytest.raises(IntegrityError):
            s.commit()


def test_ac9_session_fk_enforced_and_cascade(factory):
    sf, path = factory
    with sf() as s:
        s.add(UserSession(token_hash="a" * 64, user_id=999, created_at=NOW, expires_at=NOW))
        with pytest.raises(IntegrityError):
            s.commit()
    with sf() as s:
        u = User(username="cascade1", password_hash="x", created_at=NOW)
        s.add(u)
        s.commit()
        s.add(UserSession(token_hash="b" * 64, user_id=u.id, created_at=NOW, expires_at=NOW))
        s.commit()
        s.delete(u)
        s.commit()
    assert sqlite3.connect(path).execute("select count(*) from sessions").fetchone()[0] == 0


def test_ac5_migration_creates_schema_with_hash_column(tmp_path):
    db = tmp_path / "mig.db"
    env = {"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{db}"}
    cmd = [sys.executable, "-m", "alembic"]
    r = subprocess.run(
        [*cmd, "upgrade", "head"], cwd=BACKEND, env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    tables = {x[0] for x in con.execute("select name from sqlite_master where type='table'")}
    assert {"users", "sessions"} <= tables
    cols = {x[1] for x in con.execute("pragma table_info(users)")}
    assert {"id", "username", "password_hash", "created_at"} <= cols
    idx = {x[1] for x in con.execute("pragma index_list(users)")}
    assert "ix_users_username" in idx
    r = subprocess.run(
        [*cmd, "downgrade", "base"], cwd=BACKEND, env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr[-800:]
