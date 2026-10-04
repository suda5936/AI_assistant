"""models와 마이그레이션(0001, 0002) 단위 테스트."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from board.models import Post, User, UserSession
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

NOW = datetime(2026, 1, 1, 12, 0, 0)
BACKEND_DIR = Path(__file__).resolve().parents[3] / "backend"


def _user(username: str = "alice") -> User:
    return User(username=username, password_hash="scrypt$x", created_at=NOW)


def _session(user_id: int, token_hash: str = "a" * 64) -> UserSession:
    return UserSession(
        token_hash=token_hash,
        user_id=user_id,
        created_at=NOW,
        expires_at=NOW + timedelta(days=7),
    )


def test_user_roundtrip(db: Session) -> None:
    db.add(_user())
    db.commit()
    loaded = db.query(User).one()
    assert loaded.id == 1
    assert loaded.username == "alice"
    assert loaded.created_at == NOW


def test_username_unique(db: Session) -> None:
    db.add(_user("alice"))
    db.commit()
    db.add(_user("alice"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_session_relationship_and_unique_token(db: Session) -> None:
    user = _user()
    db.add(user)
    db.commit()
    db.add(_session(user.id))
    db.commit()
    assert db.query(UserSession).one().user.username == "alice"
    db.add(_session(user.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_session_requires_existing_user(db: Session) -> None:
    db.add(_session(user_id=999))
    with pytest.raises(IntegrityError):
        db.commit()


def test_session_deleted_with_user(db: Session) -> None:
    user = _user()
    db.add(user)
    db.commit()
    db.add(_session(user.id))
    db.commit()
    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db.commit()
    assert db.query(UserSession).count() == 0


def test_migration_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = f"sqlite:///{tmp_path}/migrated.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    command.upgrade(config, "head")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    assert {"users", "sessions"} <= set(inspector.get_table_names())
    user_indexes = {i["name"]: i for i in inspector.get_indexes("users")}
    assert user_indexes["ix_users_username"]["unique"]
    session_indexes = {i["name"]: i for i in inspector.get_indexes("sessions")}
    assert session_indexes["ix_sessions_token_hash"]["unique"]
    assert "ix_sessions_user_id" in session_indexes
    foreign_key = inspector.get_foreign_keys("sessions")[0]
    assert foreign_key["referred_table"] == "users"
    assert foreign_key["options"]["ondelete"] == "CASCADE"

    command.downgrade(config, "base")
    remaining = set(inspect(engine).get_table_names())
    assert "users" not in remaining
    assert "sessions" not in remaining
    engine.dispose()


def _post(author_id: int, title: str = "제목", created_at: datetime = NOW) -> Post:
    return Post(title=title, content="내용\n둘째 줄", author_id=author_id, created_at=created_at)


def test_post_roundtrip_keeps_text_as_is(db: Session) -> None:
    user = _user()
    db.add(user)
    db.commit()
    db.add(_post(user.id, title="  <b>x</b>  "))
    db.commit()
    loaded = db.query(Post).one()
    assert loaded.title == "  <b>x</b>  "
    assert loaded.content == "내용\n둘째 줄"
    assert loaded.created_at == NOW
    assert loaded.author.username == "alice"


def test_post_requires_existing_author(db: Session) -> None:
    db.add(_post(author_id=999))
    with pytest.raises(IntegrityError):
        db.commit()


def test_post_author_cannot_be_deleted_while_posts_exist(db: Session) -> None:
    user = _user()
    db.add(user)
    db.commit()
    db.add(_post(user.id))
    db.commit()
    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})


@pytest.mark.parametrize("missing", ["title", "content"])
def test_post_title_and_content_not_null(db: Session, missing: str) -> None:
    user = _user()
    db.add(user)
    db.commit()
    values: dict[str, str | None] = {"title": "t", "content": "x"}
    values[missing] = None
    db.add(Post(author_id=user.id, created_at=NOW, **values))
    with pytest.raises(IntegrityError):
        db.commit()


def test_post_migration_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = f"sqlite:///{tmp_path}/posts_migrated.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    engine = create_engine(db_url)

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert "posts" in inspector.get_table_names()
    index_columns = {i["name"]: i["column_names"] for i in inspector.get_indexes("posts")}
    assert index_columns == {
        "ix_posts_created_at_id": ["created_at", "id"],
        "ix_posts_author_id": ["author_id"],
    }
    foreign_key = inspector.get_foreign_keys("posts")[0]
    assert foreign_key["referred_table"] == "users"
    assert not foreign_key["options"].get("ondelete")
    columns = {c["name"]: c for c in inspector.get_columns("posts")}
    assert set(columns) == {"id", "title", "content", "author_id", "created_at"}
    assert not any(columns[name]["nullable"] for name in ("title", "content", "author_id"))

    command.downgrade(config, "0001")
    after_downgrade = set(inspect(engine).get_table_names())
    assert "posts" not in after_downgrade
    assert {"users", "sessions"} <= after_downgrade

    command.upgrade(config, "head")
    assert "posts" in inspect(engine).get_table_names()
    engine.dispose()
