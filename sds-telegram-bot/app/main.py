"""Entry point: `python -m app` starts the bot with long polling."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

from aiogram import Bot
from aiogram.exceptions import TelegramUnauthorizedError
from pydantic import ValidationError
from sqlalchemy import text

from app.bot import CUSTOMER_COMMANDS, create_bot, create_dispatcher
from app.company import load_company_config
from app.config import Settings
from app.context import AppContext
from app.database.session import create_engine, create_session_factory
from app.services.retention import purge_expired
from app.services.tracking import build_tracking_provider
from app.utils.logging import setup_logging
from app.web import start_web_server

log = logging.getLogger("app")


def load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        # Report which settings are wrong without echoing their values.
        fields = ", ".join(".".join(str(p) for p in err["loc"]).upper() or "?" for err in exc.errors())
        print(f"Configuration error — check these environment variables: {fields}", file=sys.stderr)
        raise SystemExit(2) from None


async def wait_for_database(engine, attempts: int = 10) -> None:
    for attempt in range(1, attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:
            log.warning("database not reachable", extra={"attempt": attempt, "error": type(exc).__name__})
            if attempt == attempts:
                raise
            await asyncio.sleep(min(2 * attempt, 15))


async def notification_retry_loop(ctx: AppContext, bot: Bot) -> None:
    interval = ctx.settings.notification_retry_interval_seconds
    while True:
        await asyncio.sleep(interval)
        try:
            await ctx.notifications.dispatch(bot, now=ctx.now())
        except Exception as exc:
            log.warning("notification retry loop error", extra={"error": type(exc).__name__})


async def retention_loop(ctx: AppContext) -> None:
    while True:
        try:
            await purge_expired(ctx.session_factory, retention_days=ctx.settings.data_retention_days, now=ctx.now())
        except Exception as exc:
            log.warning("retention purge failed", extra={"error": type(exc).__name__})
        await asyncio.sleep(24 * 3600)


async def run() -> None:
    settings = load_settings()
    setup_logging(settings.log_level, settings.log_format)
    company = load_company_config(settings.company_config_path)

    engine = create_engine(settings.database_url.get_secret_value())
    await wait_for_database(engine)
    ctx = AppContext(
        settings=settings,
        company=company,
        session_factory=create_session_factory(engine),
        tracking=build_tracking_provider(settings.tracking_provider),
    )
    await ctx.admin.sync_admins(settings.admin_telegram_ids)

    bot = create_bot(settings.bot_token.get_secret_value())
    dp = create_dispatcher(ctx)
    background: list[asyncio.Task] = []
    web_runner = None
    try:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            log.error("Telegram rejected BOT_TOKEN — check the token from @BotFather")
            raise SystemExit(2) from None
        await bot.set_my_commands(CUSTOMER_COMMANDS)
        log.info("bot starting", extra={"username": me.username, "environment": settings.environment})
        background = [
            asyncio.create_task(notification_retry_loop(ctx, bot), name="notification-retry"),
            asyncio.create_task(retention_loop(ctx), name="retention"),
        ]
        # Deliver anything left pending from before a restart.
        await ctx.notifications.dispatch(bot, now=ctx.now())
        if settings.web_enabled:
            web_runner = await start_web_server(ctx, bot)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=True)
    finally:
        if web_runner is not None:
            await web_runner.cleanup()
        for task in background:
            task.cancel()
        for task in background:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await ctx.drain()
        await bot.session.close()
        await engine.dispose()
        log.info("bot stopped")


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run())


if __name__ == "__main__":
    main()
