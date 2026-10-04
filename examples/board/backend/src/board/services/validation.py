"""가입 입력값 검증."""

import re
from typing import Final

from board.errors import FieldError, ValidationFailedError

USERNAME_MIN_LENGTH: Final = 4
USERNAME_MAX_LENGTH: Final = 20
PASSWORD_MIN_LENGTH: Final = 8
PASSWORD_MAX_LENGTH: Final = 72
POST_TITLE_MAX_LENGTH: Final = 100
POST_CONTENT_MAX_LENGTH: Final = 5000

_USERNAME_PATTERN: Final = re.compile(
    rf"[A-Za-z0-9_]{{{USERNAME_MIN_LENGTH},{USERNAME_MAX_LENGTH}}}"
)


def check_username(raw: str) -> tuple[str | None, FieldError | None]:
    """아이디를 검사한다. 통과하면 (소문자 아이디, None), 아니면 (None, 오류)."""
    if not raw.strip():
        return None, FieldError("username", "아이디를 입력해 주세요.")
    if _USERNAME_PATTERN.fullmatch(raw) is None:
        return None, FieldError(
            "username", "아이디는 영문 소문자, 숫자, 밑줄(_)로 4~20자여야 합니다."
        )
    return raw.lower(), None


def check_password(password: str) -> FieldError | None:
    """비밀번호를 검사해 처음 해당하는 오류 하나를 돌려준다. 통과하면 None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return FieldError("password", "비밀번호는 8자 이상이어야 합니다.")
    if len(password) > PASSWORD_MAX_LENGTH:
        return FieldError("password", "비밀번호는 72자 이하여야 합니다.")
    try:
        password.encode("utf-8")
    except UnicodeEncodeError:
        return FieldError("password", "비밀번호에 사용할 수 없는 문자가 포함되어 있습니다.")
    return None


def validate_signup(username_raw: str, password: str) -> str:
    """가입 입력값을 검사하고 정규화된 아이디를 돌려준다.

    Raises:
        ValidationFailedError: 오류가 하나라도 있을 때 (username, password 순서)
    """
    username, username_error = check_username(username_raw)
    password_error = check_password(password)
    errors = [error for error in (username_error, password_error) if error is not None]
    if errors or username is None:
        raise ValidationFailedError(errors)
    return username


def _check_post_text(field: str, label: str, value: str, max_length: int) -> FieldError | None:
    """글 필드 하나를 검사해 처음 해당하는 오류 하나를 돌려준다. 통과하면 None."""
    if not value.strip():
        return FieldError(field, f"{label}을 입력해 주세요.")
    if len(value) > max_length:
        return FieldError(field, f"{label}은 {max_length}자 이하여야 합니다.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return FieldError(field, f"{label}에 사용할 수 없는 문자가 포함되어 있습니다.")
    return None


def validate_post(title: str, content: str) -> None:
    """글 제목·내용을 검사한다. 값은 다듬지 않는다.

    Raises:
        ValidationFailedError: 오류가 하나라도 있을 때 (title, content 순서)
    """
    checked = (
        _check_post_text("title", "제목", title, POST_TITLE_MAX_LENGTH),
        _check_post_text("content", "내용", content, POST_CONTENT_MAX_LENGTH),
    )
    errors = [error for error in checked if error is not None]
    if errors:
        raise ValidationFailedError(errors)
