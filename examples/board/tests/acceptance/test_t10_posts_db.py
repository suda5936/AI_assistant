"""T-10: posts 테이블 마이그레이션 (docs/02_design.md "DB 스키마 (M2 추가)")."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from board.db import Base, create_db_engine
from board.models import Post, User, UserSession

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def _alembic(db, *args):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": f"sqlite:///{db}"},
        capture_output=True,
        text=True,
    )


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "t10.db"
    r = _alembic(path, "upgrade", "head")
    assert r.returncode == 0, r.stderr[-800:]
    return path


def _con(db):
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def _tables(con):
    return {r[0] for r in con.execute("select name from sqlite_master where type='table'")}


def test_db_posts_table_columns_match_design(db):
    con = _con(db)
    cols = {r[1]: r for r in con.execute("PRAGMA table_info(posts)")}
    assert set(cols) == {"id", "title", "content", "author_id", "created_at"}
    assert cols["id"][2].upper() == "INTEGER" and cols["id"][5] == 1
    assert cols["title"][2].upper().replace(" ", "") == "VARCHAR(100)"
    assert cols["content"][2].upper() == "TEXT"
    assert cols["author_id"][2].upper() == "INTEGER"
    assert cols["created_at"][2].upper() in ("DATETIME", "TIMESTAMP")
    for name in ("title", "content", "author_id", "created_at"):
        assert cols[name][3] == 1, f"{name} must be NOT NULL"


def test_db_posts_author_fk_references_users_without_on_delete(db):
    con = _con(db)
    fks = con.execute("PRAGMA foreign_key_list(posts)").fetchall()
    assert len(fks) == 1
    fk = fks[0]
    assert (fk[2], fk[3], fk[4]) == ("users", "author_id", "id")
    assert fk[6] in ("NO ACTION", "")  # ON DELETE 미지정


def test_db_posts_indexes_match_design(db):
    con = _con(db)
    idx = {r[1] for r in con.execute("PRAGMA index_list(posts)")}
    assert "ix_posts_created_at_id" in idx
    assert "ix_posts_author_id" in idx
    info = con.execute("PRAGMA index_info(ix_posts_created_at_id)").fetchall()
    assert [r[2] for r in info] == ["created_at", "id"]
    info = con.execute("PRAGMA index_info(ix_posts_author_id)").fetchall()
    assert [r[2] for r in info] == ["author_id"]


def test_db_fk_rejects_unknown_author_and_nulls(db):
    con = _con(db)
    ts = "2026-01-01 00:00:00"
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "insert into posts(title, content, author_id, created_at) values ('t','c',999,?)",
            (ts,),
        )
    con.execute(
        "insert into users(username,password_hash,created_at) values ('bob_1','x',?)", (ts,)
    )
    uid = con.execute("select id from users").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "insert into posts(title, content, author_id, created_at) values (NULL,'c',?,?)",
            (uid, ts),
        )
    con.execute(
        "insert into posts(title, content, author_id, created_at) values ('t','c',?,?)",
        (uid, ts),
    )
    with pytest.raises(sqlite3.IntegrityError):  # 글이 있는 사용자는 삭제 불가
        con.execute("delete from users where id=?", (uid,))


def test_db_m1_tables_still_present_after_upgrade(db):
    assert {"users", "sessions", "posts"} <= _tables(_con(db))


def test_db_downgrade_0001_then_upgrade_head_roundtrip(db):
    r = _alembic(db, "downgrade", "0001")
    assert r.returncode == 0, r.stderr[-800:]
    tables = _tables(_con(db))
    assert "posts" not in tables and {"users", "sessions"} <= tables
    r = _alembic(db, "upgrade", "head")
    assert r.returncode == 0, r.stderr[-800:]
    assert "posts" in _tables(_con(db))


def test_db_upgrade_head_twice_is_idempotent(db):
    r = _alembic(db, "upgrade", "head")
    assert r.returncode == 0, r.stderr[-800:]


def test_db_create_all_makes_every_table_including_posts(tmp_path):
    path = tmp_path / "ca.db"
    Base.metadata.create_all(create_db_engine(f"sqlite:///{path}"))
    expected = {User.__tablename__, UserSession.__tablename__, Post.__tablename__}
    assert expected == {"users", "sessions", "posts"}
    assert expected <= set(Base.metadata.tables)
    assert {"users", "sessions", "posts"} <= _tables(sqlite3.connect(path))
