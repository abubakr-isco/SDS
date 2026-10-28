from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app import texts
from app.context import AppContext
from app.handlers.common import reset_to_menu, show
from app.keyboards.callbacks import MenuCB
from app.keyboards.main import about_kb, main_menu_kb
from app.states import QuoteForm

log = logging.getLogger(__name__)


async def cmd_start(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if await state.get_state() == QuoteForm.phone.state:
        await message.answer("Starting over.", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    await message.answer(texts.welcome(ctx.company), reply_markup=main_menu_kb())


async def cmd_help(message: Message, ctx: AppContext) -> None:
    try:
        is_admin = await ctx.admin.get_active_admin(message.from_user.id) is not None
    except Exception:
        log.warning("admin lookup failed during /help")
        is_admin = False
    await message.answer(texts.help_text(is_admin), reply_markup=main_menu_kb())


async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL, reply_markup=main_menu_kb())
        return
    await reset_to_menu(message, state, texts.CANCELLED)


async def cmd_myid(message: Message) -> None:
    # A user's own ID is not secret; SDS staff use it to become administrators (ADMIN_TELEGRAM_IDS).
    await message.answer(f"Your Telegram user ID: <code>{message.from_user.id}</code>")


async def menu_home(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if await state.get_state() is not None:
        await reset_to_menu(callback, state, "Returned to the main menu. Nothing was submitted.")
        return
    await show(callback, texts.welcome(ctx.company), main_menu_kb())


async def menu_about(callback: CallbackQuery, ctx: AppContext) -> None:
    await show(callback, texts.about(ctx.company), about_kb())


def build_router() -> Router:
    router = Router(name="start")
    router.message.register(cmd_start, CommandStart())
    router.message.register(cmd_help, Command("help"))
    router.message.register(cmd_cancel, Command("cancel"))
    router.message.register(cmd_myid, Command("myid"))
    router.callback_query.register(menu_home, MenuCB.filter(F.action == "home"))
    router.callback_query.register(menu_about, MenuCB.filter(F.action == "about"))
    return router
