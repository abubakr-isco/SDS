"""Alembic environment (async). Uses DATABASE_URL; the bot token is not required for migrations."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import DatabaseSettings
from app.database.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    # Tests (and tooling) may pass a URL explicitly via `-x url=...` or config attributes.
    return (
        config.attributes.get("url")
        or context.get_x_argument(as_dictionary=True).get("url")
        or (
            DatabaseSettings().database_url.get_secret_value()  # type: ignore[call-arg]
        )
    )


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif (existing := config.attributes.get("connection")) is not None:
    _run(existing)  # connection supplied programmatically (tests)
else:
    asyncio.run(run_migrations_online())
