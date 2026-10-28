"""Alembic migrations against PostgreSQL (skipped on the SQLite default run)."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.config import PROJECT_ROOT
from app.database.models import Base
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to a PostgreSQL test database")


def _upgrade(connection, revision="head"):
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, revision)


def _downgrade(connection, revision="base"):
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.attributes["connection"] = connection
    command.downgrade(cfg, revision)


async def test_migrations_match_models_and_round_trip(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await conn.run_sync(_upgrade)
        diff = await conn.run_sync(lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata))
        assert diff == []
        await conn.run_sync(_downgrade)
        remaining = await conn.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name <> 'alembic_version'"
            )
        )
        assert remaining == 0
        await conn.run_sync(_upgrade)
        checks = await conn.scalar(
            text("SELECT count(*) FROM pg_constraint WHERE contype='c' AND connamespace='public'::regnamespace")
        )
        assert checks == 6  # status / event type / source columns are constrained in the database itself
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
