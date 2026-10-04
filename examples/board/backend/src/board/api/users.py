"""회원가입 라우터."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from board.api.deps import get_db
from board.schemas.error import ErrorResponse
from board.schemas.user import SignupRequest, UserOut
from board.services.users import create_user
from board.timeutil import utc_now

router = APIRouter(prefix="/api/users")


@router.post(
    "",
    status_code=201,
    response_model=UserOut,
    responses={
        409: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def signup(body: SignupRequest, db: Annotated[Session, Depends(get_db)]) -> UserOut:
    """회원가입."""
    user = create_user(db, body.username, body.password, utc_now())
    return UserOut.from_model(user)
