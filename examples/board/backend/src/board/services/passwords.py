"""scrypt 비밀번호 해시 (docs/adr/0001-auth-storage.md)."""

import base64
import binascii
import hashlib
import hmac
import secrets
from typing import Final

SCRYPT_N: Final = 16384
SCRYPT_R: Final = 8
SCRYPT_P: Final = 1
SCRYPT_DKLEN: Final = 64
SALT_BYTES: Final = 16
_SCHEME: Final = "scrypt"
_MAX_MEMORY: Final = 64 * 1024 * 1024


def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    """scrypt 키를 계산한다."""
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=_MAX_MEMORY
    )


def hash_password(password: str) -> str:
    """무작위 솔트로 'scrypt$n$r$p$<salt_b64>$<hash_b64>' 문자열을 만든다."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"{_SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_b64}${digest_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    """저장된 해시와 비밀번호가 일치하는지 확인한다. 형식이 깨졌으면 False."""
    parts = stored_hash.split("$")
    if len(parts) != 6 or parts[0] != _SCHEME:
        return False
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        expected = base64.b64decode(parts[5], validate=True)
        actual = _derive(password, salt, n, r, p, len(expected))
    except (ValueError, binascii.Error, OverflowError, MemoryError):
        return False
    return hmac.compare_digest(actual, expected)


_DUMMY_HASH: Final = hash_password("dummy-password-for-timing")


def verify_dummy(password: str) -> None:
    """없는 아이디 로그인 시 응답 시간을 맞추려고 더미 해시로 검증을 수행한다."""
    verify_password(password, _DUMMY_HASH)
