from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import texts
from app.context import AppContext
from app.handlers.common import show
from app.keyboards.callbacks import MenuCB
from app.keyboards.main import home_button
from app.services.tracking import TrackingOutcome
from app.states import TrackingForm

log = logging.getLogger(__name__)

QUOTE_ID = re.compile(r"^SDS-Q-\d{4}-\d{4,}$", re.IGNORECASE)
REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{2,39}$")


def _after_lookup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Look up another", callback_data=MenuCB(action="track").pack())],
            [InlineKeyboardButton(text="☎️ Contact SDS", callback_data=MenuCB(action="contact").pack())],
            [home_button()],
        ]
    )


async def start_tracking(event: CallbackQuery | Message, state: FSMContext) -> None:
    await state.set_state(TrackingForm.reference)
    await show(event, texts.TRACK_PROMPT, InlineKeyboardMarkup(inline_keyboard=[[home_button()]]))


async def receive_reference(message: Message, state: FSMContext, ctx: AppContext) -> None:
    reference = message.text.strip()
    if not REFERENCE.fullmatch(reference):
        await message.answer(texts.TRACK_INVALID, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[home_button()]]))
        return
    # Rate limit lookups so references can't be enumerated.
    if not ctx.tracking_limiter.hit(message.from_user.id):
        await state.clear()
        await message.answer(texts.TRACK_SLOW_DOWN, reply_markup=_after_lookup_kb())
        return
    await state.clear()
    tz = ctx.settings.tz

    if QUOTE_ID.fullmatch(reference):
        request = await ctx.quotes.status_for_customer(reference, message.from_user.id)
        text = texts.customer_quote_status(request, tz) if request else texts.QUOTE_NOT_FOUND
        await message.answer(text, reply_markup=_after_lookup_kb())
        return

    result = await ctx.tracking.lookup(reference.upper(), message.from_user.id)
    if result.outcome == TrackingOutcome.FOUND and result.status:
        text = texts.tracking_found(result.reference, result.status, result.last_updated, tz)
    elif result.outcome == TrackingOutcome.NOT_FOUND:
        text = texts.TRACKING_NOT_FOUND
    else:
        text = texts.TRACKING_UNAVAILABLE
    await message.answer(text, reply_markup=_after_lookup_kb())


async def non_text_reference(message: Message) -> None:
    await message.answer(
        "Please send the reference as text.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[home_button()]])
    )


def build_router() -> Router:
    router = Router(name="tracking")
    router.callback_query.register(start_tracking, MenuCB.filter(F.action == "track"))
    router.message.register(start_tracking, Command("track"))
    router.message.register(receive_reference, TrackingForm.reference, F.text)
    router.message.register(non_text_reference, TrackingForm.reference)
    return router
