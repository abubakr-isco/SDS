from __future__ import annotations

import asyncio
import logging

from aiogram import Router
from aiogram.types import ErrorEvent
from sqlalchemy.exc import SQLAlchemyError

from app import texts
from app.services.admin import NotAuthorized

log = logging.getLogger(__name__)

DB_UNAVAILABLE = "Our system is temporarily unavailable. Please try again in a few minutes, or contact SDS directly."


async def on_error(event: ErrorEvent) -> bool:
    exc = event.exception
    update = event.update
    message = update.message or (update.callback_query.message if update.callback_query else None)
    user_id = (
        update.message.from_user.id
        if update.message and update.message.from_user
        else update.callback_query.from_user.id
        if update.callback_query
        else None
    )

    if isinstance(exc, NotAuthorized):
        # Admin rights were revoked between the router filter and the service call.
        text = texts.NOT_AUTHORIZED
        log.warning("admin authorization failed in service layer", extra={"update_id": update.update_id})
    elif isinstance(exc, (SQLAlchemyError, OSError, ConnectionError, asyncio.TimeoutError)):
        text = DB_UNAVAILABLE
        log.error("database unavailable", extra={"update_id": update.update_id, "error": type(exc).__name__})
    else:
        text = texts.GENERIC_ERROR
        log.error("unhandled error", extra={"update_id": update.update_id, "error": type(exc).__name__}, exc_info=exc)

    # Never send exception details to the user.
    try:
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        elif message is not None and user_id is not None:
            await message.answer(text)
    except Exception:
        log.warning("could not deliver error message", extra={"update_id": update.update_id})
    return True


def build_router() -> Router:
    router = Router(name="errors")
    router.errors.register(on_error)
    return router
