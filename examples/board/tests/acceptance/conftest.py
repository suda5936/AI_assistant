"""인수 테스트 공용 설정. 테이블 목록을 직접 나열하지 않고 모든 모델을 등록한다."""

import contextlib
import json
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
from board.db import Base, create_db_engine, create_session_factory
from board.main import create_app
from board.models import Post, User, UserSession
from board.services.users import create_user
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[2] / "backend"

ALL_MODELS = (User, UserSession, Post)


T0 = datetime(2026, 10, 3, 1, 0, 0)


@pytest.fixture
def db(all_tables_engine):
    session = create_session_factory(all_tables_engine)()
    yield session
    session.close()


@pytest.fixture
def snapshot(all_tables_engine):
    """DB 파일의 posts 전체를 raw sqlite로 읽는다(세션 캐시 영향 배제)."""
    path = all_tables_engine.url.database

    def _snap():
        con = sqlite3.connect(path)
        try:
            return con.execute(
                "select id,title,content,author_id,created_at from posts order by id"
            ).fetchall()
        finally:
            con.close()

    return _snap


@pytest.fixture
def alice(db):
    return create_user(db, "alice", "password1", T0)


@pytest.fixture
def bob(db):
    return create_user(db, "bobby", "password1", T0)


class _Client(TestClient):
    """httpx의 delete()는 본문을 받지 않으므로 json 인자를 받게 한다(설계: DELETE 본문 `{}`)."""

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


class ApiEnv:
    """HTTP 수준 게시글 인수 테스트용 환경. alice/bob은 로그인 상태, anon은 비로그인."""

    def __init__(self, app, db):
        self.db = db
        self.alice = _Client(app, raise_server_exceptions=False)
        self.bob = _Client(app, raise_server_exceptions=False)
        self.anon = _Client(app, raise_server_exceptions=False)
        for c, name in ((self.alice, "alice_01"), (self.bob, "bobby_01")):
            body = {"username": name, "password": "valid-pw-1"}
            assert c.post("/api/users", json=body).status_code == 201
            assert c.post("/api/auth/login", json=body).status_code == 200

    def rows(self):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(
                "select id,title,content,author_id,created_at from posts order by id"
            ).fetchall()
        finally:
            con.close()

    def post(self, client=None, title="제목", content="내용"):
        r = (client or self.alice).post("/api/posts", json={"title": title, "content": content})
        assert r.status_code == 201, r.text
        return r.json()

    def fill(self, n):
        return [self.post(title=f"t{i}")["id"] for i in range(n)]

    @staticmethod
    def err(r, status, code):
        assert r.status_code == status, r.text
        assert r.json()["error"]["code"] == code, r.text

    @staticmethod
    def page_ids(r):
        assert r.status_code == 200, r.text
        return [p["id"] for p in r.json()["items"]], r.json()["page"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """alembic으로 만든 DB 위에서 실제 앱을 띄운다(posts API 인수 테스트용)."""
    db = tmp_path / "api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{db}"},
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr[-800:]
    return ApiEnv(create_app(), db)


@pytest.fixture
def env25(env):
    env.ids = env.fill(25)  # 오래된 순
    return env


@pytest.fixture
def all_tables_engine(tmp_path):
    """모든 모델의 테이블을 `Base.metadata.create_all`로 만든 SQLite 엔진."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'all.db'}")
    Base.metadata.create_all(engine)
    return engine


# ---------- T-13: 실제 uvicorn 서버 + 원시 소켓 HTTP ----------

COUNT_SQL = {"users": "SELECT count(*) FROM users", "posts": "SELECT count(*) FROM posts"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, port: int, db: Path):
        self.port = port
        self.db = db

    def raw(self, data: bytes) -> tuple[int, dict, bytes]:
        """원시 바이트를 보내고 (상태, 소문자 헤더 dict(첫 값), 본문)을 돌려준다."""
        chunks = []
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as s:
            # 서버가 본문을 다 읽기 전에 응답하고 닫을 수 있다
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                s.sendall(data)
            with contextlib.suppress(ConnectionResetError, TimeoutError):
                while True:
                    c = s.recv(65536)
                    if not c:
                        break
                    chunks.append(c)
        resp = b"".join(chunks)
        assert resp.startswith(b"HTTP/1.1"), resp[:200]
        head, _, body = resp.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        headers = {}
        for ln in lines[1:]:
            k, _, v = ln.partition(":")
            headers.setdefault(k.strip().lower(), v.strip())
        return int(lines[0].split()[1]), headers, body

    def req(self, method, path, headers=(), body=b"", *, ctype="application/json", cl=True):
        hs = [f"{method} {path} HTTP/1.1", f"Host: 127.0.0.1:{self.port}", "Connection: close"]
        if ctype:
            hs.append(f"Content-Type: {ctype}")
        if cl:
            hs.append(f"Content-Length: {len(body)}")
        hs += [f"{k}: {v}" for k, v in headers]
        return self.raw(("\r\n".join(hs) + "\r\n\r\n").encode() + body)

    def get(self, path, headers=()):
        return self.req("GET", path, headers, ctype=None, cl=False)

    def count(self, table):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(COUNT_SQL[table]).fetchone()[0]
        finally:
            con.close()


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    db = tmp_path_factory.mktemp("t13") / "t13.db"
    env = {"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{db}"}
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr[-800:]
    port = _free_port()
    cmd = [sys.executable, "-m", "uvicorn", "board.main:app", "--host", "127.0.0.1"]
    proc = subprocess.Popen(
        [*cmd, "--port", str(port)],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    srv = Server(port, db)
    try:
        for _ in range(100):
            try:
                srv.get("/api/auth/me")
                break
            except (OSError, AssertionError):
                time.sleep(0.1)
        else:
            raise AssertionError("서버가 뜨지 않음")
        yield srv
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def cookie(server):
    body = json.dumps({"username": "t13_user", "password": "valid-pw-1"}).encode()
    assert server.req("POST", "/api/users", body=body)[0] == 201
    status, headers, _ = server.req("POST", "/api/auth/login", body=body)
    assert status == 200
    return headers["set-cookie"].split(";")[0]


@pytest.fixture
def padded():
    """정확히 n바이트인 유효 JSON(끝 공백 패딩)을 만드는 함수."""

    def _make(n, title="t13", content="padded"):
        base = json.dumps({"title": title, "content": content}).encode()
        assert len(base) <= n
        return base + b" " * (n - len(base))

    return _make


@pytest.fixture
def code():
    def _code(body: bytes) -> str:
        return json.loads(body)["error"]["code"]

    return _code
