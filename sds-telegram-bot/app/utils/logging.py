"""Structured logging with personal data and secrets redacted.

Handlers never log message text on purpose; the redaction filter is a
safety net for anything that slips through (exceptions, library logs).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Telegram bot tokens: 123456789:AA... (35 chars)
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"), "<bot-token>"),
    # Passwords inside connection URLs
    (re.compile(r"(\w+://[^:/\s]+:)[^@\s]+@"), r"\1<password>@"),
    # SQLAlchemy statement parameters
    (re.compile(r"\[parameters: .*?\]", re.DOTALL), "[parameters: <redacted>]"),
    # Email addresses
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "<email>"),
    # Phone numbers written with + or common US separators
    (re.compile(r"\+\d[\d\s().-]{6,}\d"), "<phone>"),
    (re.compile(r"\(\d{3}\)\s?\d{3}[-.\s]\d{4}"), "<phone>"),
    (re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"), "<phone>"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # malformed format args — keep the raw template
            message = str(record.msg)
        record.msg = redact(message)
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        record.exc_info = None if record.exc_text else record.exc_info
        return True


_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Structured extras passed via logger.info("...", extra={...})
        for key, value in vars(record).items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value if isinstance(value, (int, float, bool, type(None))) else redact(str(value))
        if record.exc_text:
            payload["exc"] = record.exc_text
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        JsonFormatter() if fmt == "json" else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # SQL echo would print parameters; keep the engine quiet.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
