"""Bot and dispatcher factories. Transport-agnostic: works with long polling (default) or webhooks."""

from __future__ import annotations

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.context import AppContext
from app.handlers import admin, contact, errors, fallback, quote, services, start, tracking
from app.middlewares.session_timeout import QuoteSessionTimeoutMiddleware
from app.middlewares.throttling import ThrottlingMiddleware

CUSTOMER_COMMANDS = [
    BotCommand(command="start", description="Main menu"),
    BotCommand(command="quote", description="Request a freight quote"),
    BotCommand(command="track", description="Check a request or shipment"),
    BotCommand(command="contact", description="Contact SDS"),
    BotCommand(command="help", description="How to use this bot"),
    BotCommand(command="cancel", description="Cancel the current action"),
]


def create_bot(token: str) -> Bot:
    return Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))


def create_dispatcher(ctx: AppContext, storage: BaseStorage | None = None) -> Dispatcher:
    dp = Dispatcher(storage=storage or MemoryStorage(), ctx=ctx)

    # The bot is meant for one-to-one chats only.
    dp.message.filter(F.chat.type == ChatType.PRIVATE)

    throttling = ThrottlingMiddleware(ctx.flood_limiter)
    dp.message.outer_middleware(throttling)
    dp.callback_query.outer_middleware(throttling)

    timeout = QuoteSessionTimeoutMiddleware(ctx)
    dp.message.middleware(timeout)
    dp.callback_query.middleware(timeout)

    dp.include_routers(
        errors.build_router(),
        start.build_router(),
        admin.build_router(),
        admin.build_denied_router(),
        services.build_router(),
        contact.build_router(),
        tracking.build_router(),
        quote.build_router(),
        fallback.build_router(),
    )
    return dp
