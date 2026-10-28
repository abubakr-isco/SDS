from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app import texts
from app.context import AppContext
from app.handlers.common import show
from app.keyboards.callbacks import MenuCB
from app.keyboards.main import contact_kb
from app.services.contact import load_contact


async def show_contact(event: CallbackQuery | Message, ctx: AppContext) -> None:
    info = await load_contact(ctx.company, ctx.session_factory)
    await show(event, texts.contact(info, ctx.company, development=ctx.settings.is_development), contact_kb(info))


def build_router() -> Router:
    router = Router(name="contact")
    router.callback_query.register(show_contact, MenuCB.filter(F.action == "contact"))
    router.message.register(show_contact, Command("contact"))
    return router
