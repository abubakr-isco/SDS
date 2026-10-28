from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app import texts
from app.keyboards.main import main_menu_kb


async def unknown_message(message: Message) -> None:
    await message.answer(texts.UNKNOWN_INPUT, reply_markup=main_menu_kb())


async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("This button is no longer active. Use /start to open the menu.", show_alert=True)


def build_router() -> Router:
    router = Router(name="fallback")
    router.message.register(unknown_message)
    router.callback_query.register(unknown_callback)
    return router
