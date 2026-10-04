"""환경변수에서 읽는 설정."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

SESSION_COOKIE_NAME: Final = "board_session"

MAX_REQUEST_BODY_BYTES: Final = 64 * 1024  # 65536. 환경변수로 받지 않는다

SECURITY_HEADERS: Final[Mapping[str, str]] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

_TRUE_VALUES: Final = frozenset({"true", "1", "yes"})
_FALSE_VALUES: Final = frozenset({"false", "0", "no", ""})


@dataclass(frozen=True)
class Settings:
    """앱 설정. 세션 유지 기간은 환경변수로 받지 않는다."""

    database_url: str = "sqlite:///./board.db"
    session_cookie_secure: bool = False
    session_ttl: timedelta = timedelta(days=7)


def _parse_bool(name: str, raw: str) -> bool:
    """허용된 문자열을 bool로 바꾼다."""
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} 값이 올바르지 않습니다: {raw!r} (true/false/1/0/yes/no)")


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """환경변수(기본 os.environ)에서 DATABASE_URL, SESSION_COOKIE_SECURE를 읽는다.

    Raises:
        ValueError: SESSION_COOKIE_SECURE 값이 허용 목록에 없을 때
    """
    env = os.environ if environ is None else environ
    defaults = Settings()
    return Settings(
        database_url=env.get("DATABASE_URL") or defaults.database_url,
        session_cookie_secure=_parse_bool(
            "SESSION_COOKIE_SECURE", env.get("SESSION_COOKIE_SECURE", "")
        ),
    )
