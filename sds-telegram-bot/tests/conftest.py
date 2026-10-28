"""Shared fixtures.

Database: SQLite (aiosqlite) in a temp file by default — fully isolated, no setup.
Set TEST_DATABASE_URL=postgresql+asyncpg://... to run the same suite against PostgreSQL
(use a dedicated, disposable test database: tables are dropped and recreated per test).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from app.bot import create_dispatcher
from app.company import CompanyConfig, load_company_config
from app.config import PROJECT_ROOT, Settings
from app.context import AppContext
from app.database.models import Base
from app.database.session import create_engine, create_session_factory
from app.keyboards.callbacks import MenuCB, QuoteCB
from app.services.tracking import NotConfiguredTrackingProvider
from tests.harness import BOT_TOKEN, Harness, MockedBot

ADMIN_ID = 900_001
ADMIN_2_ID = 900_002
CUSTOMER_ID = 100_001
OTHER_CUSTOMER_ID = 100_002

# 10:00 AM in Chicago (CDT) on Wednesday, Oct 28 2026.
FIXED_NOW = datetime(2026, 10, 28, 15, 0, tzinfo=UTC)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def is_postgres() -> bool:
    return bool(TEST_DATABASE_URL)


@pytest_asyncio.fixture
async def engine(tmp_path):
    url = TEST_DATABASE_URL or f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine):
    return create_session_factory(engine)


def make_settings(**overrides) -> Settings:
    values = dict(
        bot_token=BOT_TOKEN,
        database_url="sqlite+aiosqlite:///unused.db",
        environment="production",
        timezone="America/Chicago",
        admin_telegram_ids=[ADMIN_ID],
        quote_session_timeout_minutes=60,
        quote_submissions_per_hour=3,
        tracking_lookups_per_10_minutes=5,
        data_retention_days=730,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)  # never read a developer's real .env in tests


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def company() -> CompanyConfig:
    config = load_company_config(PROJECT_ROOT / "config" / "company.toml")
    # Tests run with two services "confirmed" to exercise the enabled path.
    for service in config.services:
        service.enabled = service.key in {"ftl", "ltl"}
    return config


@pytest.fixture
def clock() -> Clock:
    return Clock(FIXED_NOW)


@pytest_asyncio.fixture
async def ctx(settings, company, session_factory, clock) -> AppContext:
    context = AppContext(
        settings=settings,
        company=company,
        session_factory=session_factory,
        tracking=NotConfiguredTrackingProvider(),
        clock=clock,
    )
    await context.admin.sync_admins(settings.admin_telegram_ids)
    return context


@pytest.fixture
def bot() -> MockedBot:
    return MockedBot()


@pytest_asyncio.fixture
async def h(ctx, bot) -> Harness:
    harness = Harness(create_dispatcher(ctx), bot)
    yield harness
    await ctx.drain()


# ------------------------------------------------------------------ quote helpers

QUOTE_ANSWERS = [
    ("text", "Jane Carter"),
    ("text", "Acme Logistics"),
    ("text", "Jane@Acme-Logistics.com"),
    ("text", "+1 (215) 555-0123"),
    ("text", "Dallas, TX 75201"),
    ("text", "Atlanta, Georgia"),
    ("text", "11/04/2026"),
    ("click", QuoteCB(action="freight", value="general")),
    ("text", "42,000 lb"),
    ("text", "22 pallets, dock to dock. Liftgate not needed."),
]


async def fill_quote(h: Harness, user_id: int = CUSTOMER_ID):
    """Walk through the wizard up to the review screen; returns the requests of the last step."""
    await h.click(user_id, MenuCB(action="quote"))
    requests = []
    for kind, value in QUOTE_ANSWERS:
        requests = await (h.send(user_id, value) if kind == "text" else h.click(user_id, value))
    return requests


async def submit_quote(h: Harness, user_id: int = CUSTOMER_ID):
    await fill_quote(h, user_id)
    return await h.click(user_id, QuoteCB(action="submit"))
