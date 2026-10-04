"""로그인·로그아웃·현재 사용자 라우터."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from board.api.deps import get_current_user, get_db, get_session_token, get_settings
from board.config import SESSION_COOKIE_NAME, Settings
from board.models import User
from board.schemas.error import ErrorResponse
from board.schemas.user import LoginRequest, UserOut
from board.services.sessions import create_session, delete_session
from board.services.users import authenticate
from board.timeutil import utc_now

router = APIRouter(prefix="/api/auth")


@router.post(
    "/login",
    response_model=UserOut,
    responses={
        401: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserOut:
    """로그인. 성공하면 세션 쿠키를 내려준다."""
    user = authenticate(db, body.username, body.password)
    token = create_session(db, user, utc_now(), settings.session_ttl)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(settings.session_ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    return UserOut.from_model(user)


@router.post("/logout", status_code=204, responses={415: {"model": ErrorResponse}})
def logout(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(get_session_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """로그아웃. 세션을 지우고 쿠키를 만료시킨다. 쿠키가 없어도 204."""
    if token is not None:
        delete_session(db, token)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


@router.get("/me", response_model=UserOut, responses={401: {"model": ErrorResponse}})
def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    """현재 로그인한 사용자."""
    return UserOut.from_model(user)
