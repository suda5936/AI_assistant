"""라우터 공용 의존성."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from board.config import SESSION_COOKIE_NAME, Settings
from board.errors import NotAuthenticatedError
from board.models import User
from board.services.sessions import get_user_by_token
from board.timeutil import utc_now


def get_settings(request: Request) -> Settings:
    """앱 설정."""
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[Session]:
    """요청마다 DB 세션을 열고 끝나면 닫는다."""
    with request.app.state.session_factory() as session:
        yield session


def get_session_token(request: Request) -> str | None:
    """세션 쿠키 값. 없거나 빈 문자열이면 None."""
    return request.cookies.get(SESSION_COOKIE_NAME) or None


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(get_session_token)],
) -> User:
    """현재 로그인한 사용자.

    Raises:
        NotAuthenticatedError: 토큰이 없거나 유효한 세션이 아닐 때
    """
    if token is None:
        raise NotAuthenticatedError
    user = get_user_by_token(db, token, utc_now())
    if user is None:
        raise NotAuthenticatedError
    return user
