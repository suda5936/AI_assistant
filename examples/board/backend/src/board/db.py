"""SQLAlchemy 기반 클래스, 엔진, 세션 팩토리."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry


class Base(DeclarativeBase):
    """모든 모델의 기반 클래스."""


def _enable_sqlite_foreign_keys(
    dbapi_connection: DBAPIConnection, _record: ConnectionPoolEntry
) -> None:
    """SQLite 연결마다 외래 키 제약을 켠다."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_db_engine(database_url: str) -> Engine:
    """엔진을 만든다. sqlite면 check_same_thread=False, 연결마다 PRAGMA foreign_keys=ON."""
    if database_url.startswith("sqlite"):
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    return create_engine(database_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """expire_on_commit=False인 세션 팩토리를 만든다."""
    return sessionmaker(bind=engine, expire_on_commit=False)
