"""시각 유틸. DB와 코드 안의 시각은 항상 naive UTC다."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """현재 UTC 시각을 tzinfo 없는(naive) datetime으로 돌려준다. 마이크로초는 0으로 자른다."""
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def to_iso_utc(value: datetime) -> str:
    """naive UTC datetime을 'YYYY-MM-DDTHH:MM:SSZ' 문자열로 바꾼다."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
