from datetime import timedelta

import pytest
from board.config import SESSION_COOKIE_NAME, Settings, load_settings


def test_defaults_when_environment_is_empty() -> None:
    settings = load_settings({})
    assert settings == Settings()
    assert settings.database_url == "sqlite:///./board.db"
    assert settings.session_cookie_secure is False
    assert settings.session_ttl == timedelta(days=7)


def test_cookie_name() -> None:
    assert SESSION_COOKIE_NAME == "board_session"


def test_database_url_is_read() -> None:
    assert load_settings({"DATABASE_URL": "sqlite:///x.db"}).database_url == "sqlite:///x.db"


def test_empty_database_url_falls_back_to_default() -> None:
    assert load_settings({"DATABASE_URL": ""}).database_url == Settings().database_url


@pytest.mark.parametrize("raw", ["true", "1", "yes", "TRUE", "Yes"])
def test_secure_true_values(raw: str) -> None:
    assert load_settings({"SESSION_COOKIE_SECURE": raw}).session_cookie_secure is True


@pytest.mark.parametrize("raw", ["false", "0", "no", "", "FALSE"])
def test_secure_false_values(raw: str) -> None:
    assert load_settings({"SESSION_COOKIE_SECURE": raw}).session_cookie_secure is False


@pytest.mark.parametrize("raw", ["maybe", "2", "on"])
def test_secure_invalid_value_raises(raw: str) -> None:
    with pytest.raises(ValueError, match="SESSION_COOKIE_SECURE"):
        load_settings({"SESSION_COOKIE_SECURE": raw})


def test_reads_os_environ_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///env.db")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    settings = load_settings()
    assert settings.database_url == "sqlite:///env.db"
    assert settings.session_cookie_secure is True
