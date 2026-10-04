from datetime import UTC, datetime

from board.timeutil import to_iso_utc, utc_now


def test_utc_now_is_naive_and_without_microseconds() -> None:
    now = utc_now()
    assert now.tzinfo is None
    assert now.microsecond == 0


def test_utc_now_is_close_to_real_utc() -> None:
    real = datetime.now(UTC).replace(tzinfo=None)
    assert abs((real - utc_now()).total_seconds()) < 5


def test_to_iso_utc_format() -> None:
    assert to_iso_utc(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05Z"


def test_to_iso_utc_zero_pads() -> None:
    assert to_iso_utc(datetime(2026, 10, 3, 0, 0, 0)) == "2026-10-03T00:00:00Z"
