import json
import logging
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings
from app.database.models import Customer, QuoteRequest, QuoteRequestEvent, QuoteStatus
from app.services.retention import purge_expired
from app.utils.logging import JsonFormatter, RedactingFilter, redact
from tests.conftest import ADMIN_ID, make_settings, submit_quote
from tests.harness import BOT_TOKEN

# ------------------------------------------------------------------ retention


async def test_retention_purges_only_old_closed_requests(h, ctx, clock):
    await submit_quote(h)
    async with ctx.session_factory() as session:
        rid = await session.scalar(select(QuoteRequest.id))
    await ctx.admin.change_status(ADMIN_ID, rid, QuoteStatus.COMPLETED)

    # Not old enough yet.
    result = await purge_expired(ctx.session_factory, retention_days=730, now=clock() + timedelta(days=100))
    assert (result.requests, result.customers) == (0, 0)

    later = clock() + timedelta(days=731)
    dry = await purge_expired(ctx.session_factory, retention_days=730, now=later, dry_run=True)
    assert (dry.requests, dry.customers) == (1, 1)
    async with ctx.session_factory() as session:
        assert await session.scalar(select(func.count(QuoteRequest.id))) == 1  # dry run changed nothing

    result = await purge_expired(ctx.session_factory, retention_days=730, now=later)
    assert (result.requests, result.customers) == (1, 1)
    async with ctx.session_factory() as session:
        for model in (QuoteRequest, Customer, QuoteRequestEvent):
            assert await session.scalar(select(func.count()).select_from(model)) == 0


async def test_retention_keeps_open_requests_and_can_be_disabled(h, ctx, clock):
    await submit_quote(h)
    later = clock() + timedelta(days=2000)
    assert (await purge_expired(ctx.session_factory, retention_days=730, now=later)).requests == 0
    assert (await purge_expired(ctx.session_factory, retention_days=0, now=later)).requests == 0


# ------------------------------------------------------------------ logging


@pytest.mark.parametrize(
    ("raw", "leak"),
    [
        (f"token {BOT_TOKEN} leaked", BOT_TOKEN),
        ("customer jane.carter@acme.com called", "jane.carter@acme.com"),
        ("phone +1 (215) 555-0123 on file", "555-0123"),
        ("phone 215-555-0123", "215-555-0123"),
        ("postgresql+asyncpg://sds:SuperSecret@db:5432/sds", "SuperSecret"),
        ("[SQL: INSERT ...] [parameters: ('Jane', 'jane@x.com')]", "Jane"),
    ],
)
def test_redaction(raw, leak):
    assert leak not in redact(raw)


def test_log_records_and_tracebacks_are_redacted():
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed for %s", ("jane@acme.com",), None)
    try:
        raise ValueError("bad phone +1 215 555 0123")
    except ValueError:
        import sys

        record.exc_info = sys.exc_info()
    RedactingFilter().filter(record)
    output = JsonFormatter().format(record)
    payload = json.loads(output)
    assert payload["msg"] == "failed for <email>"
    assert "555" not in output and "<phone>" in payload["exc"]


# ------------------------------------------------------------------ configuration


def test_settings_parse_admin_ids_and_reject_bad_values():
    assert make_settings(admin_telegram_ids="111, 222").admin_telegram_ids == [111, 222]
    with pytest.raises(ValidationError):
        make_settings(admin_telegram_ids="abc")
    with pytest.raises(ValidationError):
        make_settings(timezone="Mars/Olympus")
    with pytest.raises(ValidationError):
        make_settings(bot_token="not-a-token")
    with pytest.raises(ValidationError):
        make_settings(database_url="mysql://x")


def test_missing_required_settings_are_reported(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    fields = {err["loc"][0] for err in exc.value.errors()}
    assert fields == {"bot_token", "database_url"}


def test_libpq_database_url_is_upgraded_to_async_driver():
    url = make_settings(database_url="postgresql://u:p@localhost/db").database_url.get_secret_value()
    assert url == "postgresql+asyncpg://u:p@localhost/db"


def test_web_port_follows_platform_port(monkeypatch):
    monkeypatch.delenv("WEB_PORT", raising=False)
    monkeypatch.setenv("PORT", "10000")  # Render sets PORT
    assert make_settings().web_port == 10000
    monkeypatch.setenv("WEB_PORT", "8081")  # an explicit WEB_PORT wins
    assert make_settings().web_port == 8081
    assert make_settings(web_port=9000).web_port == 9000
