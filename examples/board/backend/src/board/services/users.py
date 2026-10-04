"""사용자 가입 서비스."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from board.errors import InvalidCredentialsError, UsernameTakenError
from board.models import User
from board.services.passwords import hash_password, verify_dummy, verify_password
from board.services.validation import PASSWORD_MAX_LENGTH, validate_signup


def create_user(db: Session, username_raw: str, password: str, now: datetime) -> User:
    """가입 입력을 검증하고 사용자를 저장한다.

    Raises:
        ValidationFailedError: 입력값이 규칙에 맞지 않을 때
        UsernameTakenError: 같은 아이디가 이미 있을 때
    """
    username = validate_signup(username_raw, password)
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise UsernameTakenError
    user = User(username=username, password_hash=hash_password(password), created_at=now)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UsernameTakenError from exc
    return user


def _login_key(username_raw: str) -> str:
    """조회용 아이디. UTF-8로 인코딩할 수 없는 문자가 있으면 어떤 아이디와도 같지 않은 값."""
    try:
        username_raw.encode("utf-8")
    except UnicodeEncodeError:
        return ""
    return username_raw.lower()


def authenticate(db: Session, username_raw: str, password: str) -> User:
    """아이디와 비밀번호를 확인해 사용자를 돌려준다. 실패 원인은 구분하지 않는다.

    Raises:
        InvalidCredentialsError: 아이디가 없거나 비밀번호가 맞지 않을 때
    """
    if len(password) > PASSWORD_MAX_LENGTH:
        # 아이디 존재 여부와 무관하게 scrypt 없이 즉시 실패시켜 응답 시간을 같게 한다.
        raise InvalidCredentialsError
    user = db.scalar(select(User).where(User.username == _login_key(username_raw)))
    if user is None:
        verify_dummy(password)
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return user
