import json
from pathlib import Path

from board.config import Settings
from board.db import create_db_engine, create_session_factory
from board.main import create_app
from board.openapi_export import main as export_main
from fastapi import FastAPI
from sqlalchemy import text


def test_create_app_stores_settings_and_session_factory(settings: Settings) -> None:
    created = create_app(settings)
    assert isinstance(created, FastAPI)
    assert created.state.settings is settings
    with created.state.session_factory() as session:
        assert session.execute(text("SELECT 1")).scalar() == 1


def test_create_app_does_not_create_tables(settings: Settings) -> None:
    with create_app(settings).state.session_factory() as session:
        session.execute(text("SELECT 1"))
        assert session.execute(text("SELECT name FROM sqlite_master")).fetchall() == []


def test_sqlite_foreign_keys_are_on(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path}/fk.db")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_session_factory_does_not_expire_on_commit(tmp_path: Path) -> None:
    factory = create_session_factory(create_db_engine(f"sqlite:///{tmp_path}/s.db"))
    assert factory.kw["expire_on_commit"] is False


def test_openapi_export_writes_json(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "openapi.json"
    assert export_main([str(target)]) == 0
    assert json.loads(target.read_text(encoding="utf-8"))["info"]["title"] == "board"
