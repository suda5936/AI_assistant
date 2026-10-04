"""services/validation.py 단위 테스트."""

import pytest
from board.errors import FieldError, ValidationFailedError
from board.services.validation import (
    check_password,
    check_username,
    validate_post,
    validate_signup,
)

USERNAME_FORMAT = "아이디는 영문 소문자, 숫자, 밑줄(_)로 4~20자여야 합니다."


@pytest.mark.parametrize("raw", ["abcd", "a" * 20, "Ab_9", "ABCD_1234"])
def test_username_valid_is_lowercased(raw: str) -> None:
    assert check_username(raw) == (raw.lower(), None)


@pytest.mark.parametrize("raw", ["", " ", "   ", "\t"])
def test_username_empty_or_blank(raw: str) -> None:
    assert check_username(raw) == (None, FieldError("username", "아이디를 입력해 주세요."))


@pytest.mark.parametrize(
    "raw", ["abc", "a" * 21, "ab cd", " abcd", "abcd ", "abcd\n", "ab-cd", "아이디아이디", "ab.cd"]
)
def test_username_format_error(raw: str) -> None:
    assert check_username(raw) == (None, FieldError("username", USERNAME_FORMAT))


@pytest.mark.parametrize("password", ["a" * 8, "a" * 72, " " * 8, "가" * 8, "가" * 72])
def test_password_valid(password: str) -> None:
    assert check_password(password) is None


@pytest.mark.parametrize("password", ["", "a" * 7, "가" * 7])
def test_password_too_short(password: str) -> None:
    assert check_password(password) == FieldError("password", "비밀번호는 8자 이상이어야 합니다.")


@pytest.mark.parametrize("password", ["a" * 73, "가" * 73])
def test_password_too_long(password: str) -> None:
    assert check_password(password) == FieldError("password", "비밀번호는 72자 이하여야 합니다.")


def test_password_unencodable_char() -> None:
    assert check_password("a\ud800bcdefgh") == FieldError(
        "password", "비밀번호에 사용할 수 없는 문자가 포함되어 있습니다."
    )


def test_password_length_checked_before_encoding() -> None:
    assert check_password("\ud800") == FieldError("password", "비밀번호는 8자 이상이어야 합니다.")
    assert check_password("\ud800" * 73) == FieldError(
        "password", "비밀번호는 72자 이하여야 합니다."
    )


def test_validate_signup_returns_normalized_username() -> None:
    assert validate_signup("AbCd_1", "password1") == "abcd_1"


def test_validate_signup_collects_both_errors_username_first() -> None:
    with pytest.raises(ValidationFailedError) as info:
        validate_signup("ab", "short")
    assert [item.field for item in info.value.details] == ["username", "password"]


def test_validate_signup_single_error() -> None:
    with pytest.raises(ValidationFailedError) as info:
        validate_signup("abcd", "short")
    assert [item.field for item in info.value.details] == ["password"]


TITLE_EMPTY = FieldError("title", "제목을 입력해 주세요.")
CONTENT_EMPTY = FieldError("content", "내용을 입력해 주세요.")


def _post_errors(title: str, content: str) -> list[FieldError]:
    with pytest.raises(ValidationFailedError) as caught:
        validate_post(title, content)
    return caught.value.details


def test_post_valid_passes() -> None:
    validate_post("제목", "내용\n두 줄")


def test_post_boundary_lengths_pass() -> None:
    validate_post("t" * 100, "c" * 5000)


@pytest.mark.parametrize("blank", ["", "   ", "\n\t", "\u3000\u3000"])
def test_post_blank_fields(blank: str) -> None:
    assert _post_errors(blank, "ok") == [TITLE_EMPTY]
    assert _post_errors("ok", blank) == [CONTENT_EMPTY]


def test_post_both_blank_title_first() -> None:
    assert _post_errors("", " ") == [TITLE_EMPTY, CONTENT_EMPTY]


def test_post_too_long() -> None:
    assert _post_errors("t" * 101, "ok") == [FieldError("title", "제목은 100자 이하여야 합니다.")]
    assert _post_errors("ok", "c" * 5001) == [
        FieldError("content", "내용은 5000자 이하여야 합니다.")
    ]


def test_post_whitespace_counts_toward_length() -> None:
    validate_post(" " * 99 + "a", "ok")
    assert _post_errors(" " * 100 + "a", "ok") == [
        FieldError("title", "제목은 100자 이하여야 합니다.")
    ]


def test_post_blank_over_limit_reports_blank() -> None:
    assert _post_errors(" " * 101, "ok") == [TITLE_EMPTY]


def test_post_unencodable_characters() -> None:
    assert _post_errors("a\ud800", "ok") == [
        FieldError("title", "제목에 사용할 수 없는 문자가 포함되어 있습니다.")
    ]
    assert _post_errors("ok", "a\udc00") == [
        FieldError("content", "내용에 사용할 수 없는 문자가 포함되어 있습니다.")
    ]


def test_post_error_message_is_validation_error() -> None:
    with pytest.raises(ValidationFailedError) as caught:
        validate_post("", "")
    assert caught.value.status_code == 422
    assert caught.value.code == "validation_error"
