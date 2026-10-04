"""T-04 인수 테스트: 회원가입 API (AC-1~5, AC-10 일부)."""

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from board.main import create_app
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[2] / "backend"
J = {"Content-Type": "application/json"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t04.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{db}"},
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr[-800:]
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c, db


def _signup(c, username="alice_01", pw="valid-pw-1"):
    return c.post("/api/users", json={"username": username, "password": pw})


def _rows(db):
    con = sqlite3.connect(db)
    try:
        return con.execute("select username, password_hash from users").fetchall()
    finally:
        con.close()


def _fields(resp):
    return {d["field"]: d["message"] for d in resp.json()["error"]["details"]}


def test_ac1_valid_signup_creates_account(env):
    c, db = env
    r = _signup(c)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "alice_01"
    assert isinstance(body["id"], int) and body["created_at"]
    assert len(_rows(db)) == 1


@pytest.mark.parametrize("username", ["abcd", "a" * 20, "a_1_", "____"])
def test_ac1_username_boundaries_accepted(env, username):
    c, db = env
    assert _signup(c, username).status_code == 201
    assert len(_rows(db)) == 1


def test_ac1_uppercase_is_normalized_to_lowercase(env):
    c, db = env
    r = _signup(c, "Alice_01")
    assert r.status_code == 201, r.text
    assert r.json()["username"] == "alice_01"
    assert _rows(db)[0][0] == "alice_01"


def test_ac2_duplicate_username_rejected_no_new_account(env):
    c, db = env
    assert _signup(c).status_code == 201
    r = _signup(c, "alice_01", "other-pw-99")
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "username_taken"
    assert err["message"] == "이미 사용 중인 아이디입니다."
    assert len(_rows(db)) == 1


def test_ac2_duplicate_is_case_insensitive(env):
    c, db = env
    assert _signup(c, "alice_01").status_code == 201
    r = _signup(c, "ALICE_01")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "username_taken"
    assert len(_rows(db)) == 1


def test_ac2_repeated_duplicate_attempts_stay_409(env):
    c, db = env
    _signup(c)
    for _ in range(3):
        assert _signup(c).status_code == 409
    assert len(_rows(db)) == 1


def test_ac3_short_password_rejected_with_reason(env):
    c, db = env
    r = _signup(c, pw="a" * 7)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert _fields(r)["password"] == "비밀번호는 8자 이상이어야 합니다."
    assert _rows(db) == []


def test_ac3_empty_password_rejected(env):
    c, db = env
    r = _signup(c, pw="")
    assert r.status_code == 422
    assert _fields(r)["password"] == "비밀번호는 8자 이상이어야 합니다."
    assert _rows(db) == []


@pytest.mark.parametrize("pw", ["a" * 8, "a" * 72, "비밀번호여덟글자입니다"])
def test_ac3_password_length_boundaries_accepted(env, pw):
    c, db = env
    assert _signup(c, pw=pw).status_code == 201
    assert len(_rows(db)) == 1


def test_ac3_password_over_72_rejected(env):
    c, db = env
    r = _signup(c, pw="a" * 73)
    assert r.status_code == 422
    assert _fields(r)["password"] == "비밀번호는 72자 이하여야 합니다."
    assert _rows(db) == []


def test_ac3_surrogate_password_rejected_422_not_500(env):
    c, db = env
    body = '{"username": "alice_01", "password": "\\ud800abcdefgh"}'
    r = c.post("/api/users", content=body, headers=J)
    assert r.status_code == 422, r.text
    assert _fields(r)["password"] == "비밀번호에 사용할 수 없는 문자가 포함되어 있습니다."
    assert _rows(db) == []


@pytest.mark.parametrize("username", ["", "   ", "\t"])
def test_ac4_blank_username_rejected(env, username):
    c, db = env
    r = _signup(c, username)
    assert r.status_code == 422
    assert _fields(r)["username"] == "아이디를 입력해 주세요."
    assert _rows(db) == []


@pytest.mark.parametrize(
    "username",
    [
        "abc",
        "a" * 21,
        "alice 01",
        " alice01",
        "alice01 ",
        "alice-01",
        "앨리스앨리스",
        "ali.ce1",
        "alice\n",
    ],
)
def test_ac4_invalid_username_format_rejected(env, username):
    c, db = env
    r = _signup(c, username)
    assert r.status_code == 422, (username, r.text)
    assert _fields(r)["username"] == "아이디는 영문 소문자, 숫자, 밑줄(_)로 4~20자여야 합니다."
    assert _rows(db) == []


def test_ac4_both_fields_invalid_reports_both(env):
    c, _ = env
    r = _signup(c, "ab", "short")
    assert r.status_code == 422
    assert [d["field"] for d in r.json()["error"]["details"]] == ["username", "password"]


@pytest.mark.parametrize(
    "payload",
    [{}, {"username": "alice_01"}, {"password": "password1"}, {"username": 1234, "password": "x"}],
)
def test_ac4_missing_or_wrong_type_fields_422(env, payload):
    c, db = env
    r = c.post("/api/users", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert _rows(db) == []


def test_ac4_non_json_content_type_415(env):
    c, db = env
    r = c.post(
        "/api/users",
        content="username=alice_01&password=valid-pw-1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"
    assert _rows(db) == []


def test_ac5_db_stores_salted_hash_not_plaintext_via_api(env):
    c, db = env
    pw = "SuperSecret-pw-123"
    assert _signup(c, "alice_01", pw).status_code == 201
    assert _signup(c, "bob_0001", pw).status_code == 201
    rows = _rows(db)
    assert len(rows) == 2
    hashes = [h for _, h in rows]
    for h in hashes:
        assert pw not in h
        assert h != pw
        assert re.fullmatch(r"scrypt\$\d+\$\d+\$\d+\$[A-Za-z0-9+/=_-]+\$[A-Za-z0-9+/=_-]+", h), h
    assert hashes[0] != hashes[1]  # 같은 비밀번호도 솔트가 달라 해시가 다르다


def test_ac10_signup_response_has_no_password_or_hash(env):
    c, db = env
    pw = "SuperSecret-pw-123"
    r = _signup(c, "alice_01", pw)
    stored = _rows(db)[0][1]
    raw = r.text + str(dict(r.headers))
    assert set(r.json()) == {"id", "username", "created_at"}
    assert pw not in raw and stored not in raw
    assert "password" not in raw.lower() and "scrypt" not in raw


def test_ac10_error_responses_do_not_echo_password_or_hash(env):
    c, db = env
    pw = "SuperSecret-pw-123"
    _signup(c, "alice_01", pw)
    stored = _rows(db)[0][1]
    for r in (_signup(c, "alice_01", pw), _signup(c, "ab", pw), _signup(c, "alice_02", "short")):
        assert pw not in r.text and stored not in r.text and "scrypt" not in r.text
    r = _signup(c, "alice_02", "p" * 73)
    assert "p" * 73 not in r.text
