"""services/passwords.py 단위 테스트."""

import base64

import pytest
from board.services import passwords
from board.services.passwords import hash_password, verify_dummy, verify_password


def test_hash_format() -> None:
    stored = hash_password("correct horse")
    scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
    assert (scheme, n, r, p) == ("scrypt", "16384", "8", "1")
    assert len(base64.b64decode(salt_b64, validate=True)) == 16
    assert len(base64.b64decode(hash_b64, validate=True)) == 64
    assert "correct horse" not in stored


def test_same_password_gives_different_hashes() -> None:
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_success_and_failure() -> None:
    stored = hash_password("password1")
    assert verify_password("password1", stored) is True
    assert verify_password("password2", stored) is False
    assert verify_password("", stored) is False


def test_verify_unicode_and_boundary_length() -> None:
    long_password = "가" * 72
    stored = hash_password(long_password)
    assert verify_password(long_password, stored) is True
    assert verify_password("가" * 71, stored) is False


@pytest.mark.parametrize(
    "broken",
    [
        "",
        "plain-text",
        "scrypt$16384$8$1$onlyfive",
        "bcrypt$16384$8$1$AAAA$AAAA",
        "scrypt$x$8$1$AAAA$AAAA",
        "scrypt$16384$8$1$!!!$AAAA",
        "scrypt$16384$8$1$AAAA$!!!",
        "scrypt$16384$8$1$AAAA$AAAA$extra",
        "scrypt$0$8$1$AAAA$AAAA",
        "scrypt$16384$8$1$AAAA$",
        "scrypt$999999999999$8$1$AAAA$AAAA",
    ],
)
def test_verify_broken_hash_returns_false(broken: str) -> None:
    assert verify_password("password1", broken) is False


def test_verify_dummy_runs_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_verify(password: str, stored_hash: str) -> bool:
        calls.append((password, stored_hash))
        return False

    monkeypatch.setattr(passwords, "verify_password", fake_verify)
    assert verify_dummy("whatever") is None
    assert calls == [("whatever", passwords._DUMMY_HASH)]
    assert calls[0][1].startswith("scrypt$")


def test_hash_password_rejects_unencodable_password() -> None:
    with pytest.raises(UnicodeEncodeError):
        hash_password("a\ud800bcdefgh")


def test_verify_password_unencodable_password_returns_false() -> None:
    stored = hash_password("password1")
    assert verify_password("a\ud800bcdefgh", stored) is False
