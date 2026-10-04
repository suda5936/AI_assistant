"""Alembic 환경. DB URL은 load_settings()에서 읽는다."""

from alembic import context
from board import models
from board.config import load_settings
from board.db import Base, create_db_engine

# models를 import해야 모든 테이블이 메타데이터에 등록된다.
REGISTERED_MODELS = models.__all__
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 연결 없이 SQL만 만든다."""
    context.configure(
        url=load_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """DB에 연결해 마이그레이션을 적용한다."""
    engine = create_db_engine(load_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
