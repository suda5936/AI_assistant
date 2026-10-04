"""사용자 요청·응답 스키마."""

from pydantic import BaseModel

from board.models import User
from board.timeutil import to_iso_utc


class SignupRequest(BaseModel):
    """회원가입 요청. 검증은 services/validation.py가 맡는다."""

    username: str
    password: str


class LoginRequest(BaseModel):
    """로그인 요청."""

    username: str
    password: str


class UserOut(BaseModel):
    """사용자 응답. 비밀번호 관련 필드를 두지 않는다."""

    id: int
    username: str
    created_at: str

    @classmethod
    def from_model(cls, user: User) -> "UserOut":
        """모델에서 응답을 만든다."""
        return cls(id=user.id, username=user.username, created_at=to_iso_utc(user.created_at))
