"""백엔드 단위 테스트 공용 픽스처. 테스트마다 임시 SQLite 파일을 쓴다."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from board import models
from board.config import Settings
from board.db import Base, create_db_engine
from board.main import create_app
from board.models import User
from board.services.users import create_user
from board.timeutil import utc_now
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """테스트 전용 설정."""
    return Settings(database_url=f"sqlite:///{tmp_path}/test.db")


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """테이블이 만들어진 앱."""
    created = create_app(settings)
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    exported_tables = {getattr(models, name).__tablename__ for name in models.__all__}
    assert exported_tables <= set(inspect(engine).get_table_names())
    engine.dispose()
    return created


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    """앱과 같은 DB를 보는 세션."""
    with app.state.session_factory() as session:
        yield session


@pytest.fixture
def login_client(app: FastAPI) -> Iterator[Callable[[str], TestClient]]:
    """아이디로 로그인한 새 TestClient를 만드는 함수 (사용자마다 쿠키가 분리됨)."""
    opened: list[TestClient] = []

    def _login(name: str) -> TestClient:
        test_client = TestClient(app)
        response = test_client.post(
            "/api/auth/login", json={"username": name, "password": "password1"}
        )
        assert response.status_code == 200
        opened.append(test_client)
        return test_client

    yield _login
    for test_client in opened:
        test_client.close()


@pytest.fixture
def make_user(db: Session) -> Callable[[str], User]:
    """아이디를 받아 사용자를 만드는 함수 (비밀번호는 password1)."""

    def _make(name: str) -> User:
        return create_user(db, name, "password1", utc_now())

    return _make
