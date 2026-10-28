from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from app import texts
from app.keyboards.main import main_menu_kb
from app.states import QuoteForm


async def show(event: Message | CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Reply to a message, or replace the message a button was pressed on."""
    if isinstance(event, CallbackQuery):
        await event.answer()
        if isinstance(event.message, Message):
            try:
                await event.message.edit_text(text, reply_markup=reply_markup)
                return
            except TelegramBadRequest:
                pass  # too old to edit, or identical content — fall back to a new message
        await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
        return
    await event.answer(text, reply_markup=reply_markup)


async def send(event: Message | CallbackQuery, text: str, reply_markup=None) -> None:
    """Always send a new message (needed for reply keyboards)."""
    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.bot.send_message(event.from_user.id, text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)


async def reset_to_menu(event: Message | CallbackQuery, state: FSMContext, text: str) -> None:
    """Clear any conversation and show the main menu, removing a phone reply keyboard if one is open."""
    had_phone_keyboard = await state.get_state() == QuoteForm.phone.state
    await state.clear()
    if had_phone_keyboard:
        await send(event, text, reply_markup=ReplyKeyboardRemove())
        await send(event, texts.MAIN_MENU, reply_markup=main_menu_kb())
    else:
        await show(event, f"{text}\n\n{texts.MAIN_MENU}", reply_markup=main_menu_kb())
