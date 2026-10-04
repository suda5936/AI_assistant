"""로그인 세션 서비스. 토큰 원문은 저장하지 않고 SHA-256 해시만 저장한다."""

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from board.models import User, UserSession


def hash_token(token: str) -> str:
    """토큰의 SHA-256 hex 문자열(64자)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User, now: datetime, ttl: timedelta) -> str:
    """세션 행을 저장하고 쿠키에 담을 원본 토큰을 돌려준다."""
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            token_hash=hash_token(token), user_id=user.id, created_at=now, expires_at=now + ttl
        )
    )
    db.commit()
    return token


def _find_session(db: Session, token: str) -> UserSession | None:
    return db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))


def get_user_by_token(db: Session, token: str, now: datetime) -> User | None:
    """토큰의 사용자. 세션이 없으면 None, 만료됐으면 행을 지우고 None."""
    session = _find_session(db, token)
    if session is None:
        return None
    if session.expires_at <= now:
        db.delete(session)
        db.commit()
        return None
    return session.user


def delete_session(db: Session, token: str) -> None:
    """세션 행을 삭제한다. 없으면 아무 일도 하지 않는다."""
    session = _find_session(db, token)
    if session is not None:
        db.delete(session)
        db.commit()
