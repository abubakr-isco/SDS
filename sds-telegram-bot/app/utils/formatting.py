from __future__ import annotations

from datetime import UTC, date, datetime
from html import escape
from zoneinfo import ZoneInfo


def esc(value: object) -> str:
    """HTML-escape user-provided text for parse_mode=HTML messages."""
    return escape(str(value), quote=False)


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; everything is stored as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def fmt_date(value: date) -> str:
    return value.strftime("%a, %b %d, %Y").replace(" 0", " ")


def fmt_datetime(value: datetime, tz: ZoneInfo) -> str:
    local = as_utc(value).astimezone(tz)
    return local.strftime("%b %d, %Y %I:%M %p %Z").replace(" 0", " ")


def fmt_weight(value: int | None) -> str:
    return f"{value:,} lb" if value else "Not sure"
