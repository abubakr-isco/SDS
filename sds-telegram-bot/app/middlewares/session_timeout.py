from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, TelegramObject

from app import texts
from app.context import AppContext
from app.keyboards.main import main_menu_kb
from app.states import QuoteForm

QUOTE_STATES = {s.state for s in QuoteForm.__all_states__}


class QuoteSessionTimeoutMiddleware(BaseMiddleware):
    """Expire abandoned quote conversations after a period of inactivity."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.timeout = timedelta(minutes=ctx.settings.quote_session_timeout_minutes)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: FSMContext | None = data.get("state")
        if state is None or await state.get_state() not in QUOTE_STATES:
            return await handler(event, data)

        now = self.ctx.now()
        stored = await state.get_value("last_activity")
        if stored and now - datetime.fromisoformat(stored) > self.timeout:
            await state.clear()
            message = event.message if isinstance(event, CallbackQuery) else event
            if isinstance(event, CallbackQuery):
                await event.answer()
            if isinstance(message, Message):
                await message.answer(texts.SESSION_EXPIRED, reply_markup=ReplyKeyboardRemove())
                await message.answer(texts.MAIN_MENU, reply_markup=main_menu_kb())
            return None
        await state.update_data(last_activity=now.isoformat())
        return await handler(event, data)
