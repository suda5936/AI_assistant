"""FastAPI 앱 생성."""

from fastapi import FastAPI

from board.api.auth import router as auth_router
from board.api.middleware import (
    register_body_limit_middleware,
    register_json_only_middleware,
    register_security_headers_middleware,
)
from board.api.posts import router as posts_router
from board.api.users import router as users_router
from board.config import MAX_REQUEST_BODY_BYTES, Settings, load_settings
from board.db import create_db_engine, create_session_factory
from board.errors import register_exception_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    """앱을 만든다. settings가 None이면 load_settings()를 쓴다. 테이블은 만들지 않는다."""
    resolved = settings if settings is not None else load_settings()
    app = FastAPI(title="board", docs_url=None, redoc_url=None, openapi_url=None)
    engine = create_db_engine(resolved.database_url)
    app.state.settings = resolved
    app.state.session_factory = create_session_factory(engine)
    register_exception_handlers(app)
    # 나중에 등록한 것이 바깥에서 먼저 실행된다: 보안 헤더 -> 415 -> 411/413 -> 라우터
    register_body_limit_middleware(app, MAX_REQUEST_BODY_BYTES)
    register_json_only_middleware(app)
    register_security_headers_middleware(app)
    app.include_router(users_router)
    app.include_router(auth_router)
    app.include_router(posts_router)
    return app


app = create_app()
