"""T-05 인수 테스트: 로그인·로그아웃·me (AC-6~10, API 수준)."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from board.main import create_app
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[2] / "backend"
J = {"Content-Type": "application/json"}
PW = "valid-pw-1"
GENERIC = "아이디 또는 비밀번호가 올바르지 않습니다."


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t05.db"
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
        c.post("/api/users", json={"username": "alice_01", "password": PW})
        c.cookies.clear()
        yield c, db


def _login(c, username="alice_01", pw=PW):
    return c.post("/api/auth/login", json={"username": username, "password": pw})


def test_ac6_login_success_returns_user_and_me_shows_username(env):
    c, _ = env
    r = _login(c)
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "alice_01"
    me = c.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice_01"


def test_ac6_login_username_case_insensitive(env):
    c, _ = env
    r = _login(c, "ALICE_01")
    assert r.status_code == 200
    assert r.json()["username"] == "alice_01"


def test_ac6_me_without_login_is_401(env):
    c, _ = env
    r = c.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize(
    "username,pw",
    [
        ("alice_01", "wrong-password"),
        ("nobody_99", PW),
        ("", ""),
        ("  ", PW),
        ("alice_01", ""),
        ("alice_01", "x" * 73),
        ("alice_01", "x" * 500),
        ("a" * 100, PW),
        ("alice_01", "\ud800passw"),
        ("\ud800lice_01", PW),
    ],
)
def test_ac7_all_failures_identical(env, username, pw):
    c, _ = env
    r = c.post(
        "/api/auth/login",
        content=__import__("json").dumps({"username": username, "password": pw}),
        headers=J,
    )
    assert r.status_code == 401, r.text
    err = r.json()["error"]
    assert err["code"] == "invalid_credentials"
    assert err["message"] == GENERIC
    assert "set-cookie" not in r.headers
    assert c.get("/api/auth/me").status_code == 401


def test_ac7_wrong_password_and_unknown_user_bodies_equal(env):
    c, _ = env
    a = _login(c, pw="wrong-password")
    b = _login(c, username="nobody_99")
    assert a.status_code == b.status_code
    assert a.json() == b.json()


def test_ac7_missing_fields_422_not_logged_in(env):
    c, _ = env
    r = c.post("/api/auth/login", json={"username": "alice_01"})
    assert r.status_code == 422
    assert c.get("/api/auth/me").status_code == 401


def test_ac7_non_json_content_type_415(env):
    c, _ = env
    r = c.post(
        "/api/auth/login",
        content="username=alice_01&password=" + PW,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 415


def test_ac8_session_persists_across_requests_and_new_client(env):
    c, _ = env
    _login(c)
    token = c.cookies.get("board_session")
    assert token
    for _ in range(3):
        assert c.get("/api/auth/me").status_code == 200
    # 새 클라이언트(= 새로고침 후 쿠키만 보냄)
    with TestClient(c.app, raise_server_exceptions=False) as c2:
        r = c2.get("/api/auth/me", headers={"Cookie": f"board_session={token}"})
        assert r.status_code == 200
        assert r.json()["username"] == "alice_01"


def test_ac8_repeat_login_gives_working_sessions(env):
    c, _ = env
    _login(c)
    t1 = c.cookies.get("board_session")
    _login(c)
    t2 = c.cookies.get("board_session")
    assert t1 != t2
    assert c.get("/api/auth/me").status_code == 200


def test_ac9_logout_invalidates_old_cookie(env):
    c, _ = env
    _login(c)
    token = c.cookies.get("board_session")
    r = c.post("/api/auth/logout", json={})
    assert r.status_code == 204
    assert c.get("/api/auth/me").status_code == 401
    # 이전 쿠키를 수동으로 재전송해도 인증되지 않는다
    with TestClient(c.app, raise_server_exceptions=False) as c2:
        r = c2.get("/api/auth/me", headers={"Cookie": f"board_session={token}"})
        assert r.status_code == 401


def test_ac9_logout_clears_cookie_header(env):
    c, _ = env
    _login(c)
    r = c.post("/api/auth/logout", json={})
    sc = r.headers["set-cookie"].lower()
    assert "board_session=" in sc
    assert "max-age=0" in sc
    assert "httponly" in sc


def test_ac9_logout_without_session_is_204_and_repeatable(env):
    c, _ = env
    assert c.post("/api/auth/logout", json={}).status_code == 204
    assert c.post("/api/auth/logout", json={}).status_code == 204


def test_ac9_logout_requires_json_content_type(env):
    c, _ = env
    r = c.post("/api/auth/logout", content="", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415


def test_ac9_logout_only_affects_own_session(env):
    c, _ = env
    _login(c)
    t1 = c.cookies.get("board_session")
    c.cookies.clear()
    _login(c)
    c.post("/api/auth/logout", json={})
    with TestClient(c.app, raise_server_exceptions=False) as c2:
        r = c2.get("/api/auth/me", headers={"Cookie": f"board_session={t1}"})
        assert r.status_code == 200


def test_ac9_unknown_token_is_401(env):
    c, _ = env
    r = c.get("/api/auth/me", headers={"Cookie": "board_session=not-a-real-token"})
    assert r.status_code == 401


def test_ac9_expired_session_is_401(env):
    c, db = env
    _login(c)
    con = sqlite3.connect(db)
    con.execute("update sessions set expires_at = '2000-01-01 00:00:00.000000'")
    con.commit()
    con.close()
    assert c.get("/api/auth/me").status_code == 401


def test_ac10_cookie_attributes(env):
    c, _ = env
    r = _login(c)
    sc = r.headers["set-cookie"]
    low = sc.lower()
    assert sc.startswith("board_session=")
    assert "httponly" in low
    assert "samesite=lax" in low
    assert "path=/" in low
    assert "max-age=604800" in low
    assert "secure" not in low.replace("samesite", "")


def test_ac10_secure_flag_when_configured(tmp_path, monkeypatch):
    db = tmp_path / "sec.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{db}"},
        check=True,
        capture_output=True,
    )
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        c.post("/api/users", json={"username": "alice_01", "password": PW})
        r = _login(c)
        assert r.status_code == 200
        assert "secure" in r.headers["set-cookie"].lower().replace("samesite", "")


def test_ac10_token_not_stored_raw_and_no_secrets_in_responses(env):
    c, db = env
    r1 = _login(c)
    me = c.get("/api/auth/me")
    token = c.cookies.get("board_session")
    con = sqlite3.connect(db)
    pwhash = con.execute("select password_hash from users").fetchone()[0]
    stored = [row[0] for row in con.execute("select token_hash from sessions")]
    con.close()
    assert token not in stored
    for r in (r1, me):
        text = r.text.lower()
        assert PW not in r.text
        assert pwhash not in r.text
        assert "password" not in text
        assert "scrypt" not in text
        assert set(r.json()) == {"id", "username", "created_at"}
    # 실패 응답에도 비밀번호가 반향되지 않는다
    bad = _login(c, pw="wrong-password")
    assert "wrong-password" not in bad.text
