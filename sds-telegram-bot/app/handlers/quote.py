"""Freight quote wizard (aiogram FSM).

Answers are kept in FSM data as JSON-safe values (dates as ISO strings) so the
storage backend can be swapped for Redis without changes.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from collections.abc import Callable
from datetime import date, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from pydantic import ValidationError as PydanticValidationError

from app import texts
from app.context import AppContext
from app.handlers.common import reset_to_menu, send, show
from app.keyboards.callbacks import MenuCB, QuoteCB
from app.keyboards.main import back_home_kb
from app.keyboards.quote import (
    CANCEL_TEXT,
    company_kb,
    date_kb,
    details_kb,
    edit_kb,
    freight_kb,
    phone_reply_kb,
    review_kb,
    step_kb,
    weight_kb,
)
from app.services.quotes import PickupDateInPast, QuoteDraft, QuoteRateLimited
from app.states import QUOTE_STEPS, QuoteForm
from app.utils.validation import (
    ValidationError,
    parse_company,
    parse_details,
    parse_email,
    parse_full_name,
    parse_location,
    parse_phone,
    parse_pickup_date,
    parse_weight,
)

log = logging.getLogger(__name__)

STATE_TO_FIELD = {getattr(QuoteForm, f).state: f for f in QUOTE_STEPS}

DRAFT_FIELDS = set(QuoteDraft.model_fields)


def _keyboard(field: str, ctx: AppContext) -> InlineKeyboardMarkup:
    return {
        "full_name": lambda: step_kb(back=False),
        "company": company_kb,
        "pickup_date": date_kb,
        "freight_type": lambda: freight_kb(ctx.company),
        "weight": weight_kb,
        "details": details_kb,
    }.get(field, step_kb)()


# ----------------------------------------------------------------- navigation helpers


async def ask(event: Message | CallbackQuery, state: FSMContext, ctx: AppContext, field: str, prefix: str = "") -> None:
    await state.set_state(getattr(QuoteForm, field))
    text = (prefix + "\n\n" if prefix else "") + texts.prompt(field)
    if field == "phone":
        # Reply keyboard (share contact) can't be attached by editing; always send a new message.
        await send(event, text, reply_markup=phone_reply_kb())
    else:
        await show(event, text, _keyboard(field, ctx))


async def advance(event: Message | CallbackQuery, state: FSMContext, ctx: AppContext, field: str) -> None:
    """Go to the next step, or back to the review screen when editing a single field."""
    if field == "phone":
        await send(event, "✅ Phone number saved.", reply_markup=ReplyKeyboardRemove())
    data = await state.get_data()
    if data.get("editing"):
        await state.update_data(editing=False)
        await show_review(event, state, as_new_message=isinstance(event, Message))
        return
    index = QUOTE_STEPS.index(field)
    if index + 1 < len(QUOTE_STEPS):
        await ask(event, state, ctx, QUOTE_STEPS[index + 1])
    else:
        await show_review(event, state, as_new_message=isinstance(event, Message))


async def show_review(event: Message | CallbackQuery, state: FSMContext, *, as_new_message: bool = False) -> None:
    data = await state.get_data()
    if not data.get("submission_key"):
        # Idempotency key: double taps / retries of the same form map to one saved request.
        data["submission_key"] = str(uuid.uuid4())
        await state.update_data(submission_key=data["submission_key"])
    await state.set_state(QuoteForm.review)
    text = texts.quote_review(data)
    if as_new_message:
        await send(event, text, reply_markup=review_kb())
    else:
        await show(event, text, review_kb())


async def start_quote(
    event: Message | CallbackQuery, state: FSMContext, ctx: AppContext, service_name: str | None = None
) -> None:
    await state.clear()
    await state.set_state(QuoteForm.full_name)
    await state.update_data(requested_service=service_name, last_activity=ctx.now().isoformat())
    await show(event, texts.quote_intro(service_name), step_kb(back=False))


# ----------------------------------------------------------------- text answers


def _location(prefix: str) -> Callable[[str, AppContext], dict]:
    def parse(text: str, _ctx: AppContext) -> dict:
        loc = parse_location(text)
        return {f"{prefix}_city": loc.city, f"{prefix}_state": loc.state, f"{prefix}_zip": loc.zip_code}

    return parse


PARSERS: dict[str, Callable[[str, AppContext], dict]] = {
    "full_name": lambda t, _: {"full_name": parse_full_name(t)},
    "company": lambda t, _: {"company_name": parse_company(t)},
    "email": lambda t, _: {"email": parse_email(t)},
    "phone": lambda t, _: {"phone": parse_phone(t)},
    "pickup": _location("pickup"),
    "delivery": _location("delivery"),
    "pickup_date": lambda t, ctx: {"pickup_date": parse_pickup_date(t, ctx.today()).isoformat()},
    "weight": lambda t, _: {"estimated_weight_lb": parse_weight(t)},
    "details": lambda t, _: {"shipment_details": parse_details(t)},
}


async def text_answer(message: Message, state: FSMContext, ctx: AppContext) -> None:
    field = STATE_TO_FIELD[await state.get_state()]
    try:
        values = PARSERS[field](message.text, ctx)
    except ValidationError as exc:
        markup = phone_reply_kb() if field == "phone" else _keyboard(field, ctx)
        await message.answer(f"⚠️ {exc}", reply_markup=markup)
        return
    await state.update_data(**values)
    await advance(message, state, ctx, field)


async def shared_contact(message: Message, state: FSMContext, ctx: AppContext) -> None:
    contact = message.contact
    # Only accept the user's own number, not a forwarded contact card.
    if contact.user_id != message.from_user.id:
        await message.answer("⚠️ Please share your own phone number, or type it.", reply_markup=phone_reply_kb())
        return
    raw = contact.phone_number if contact.phone_number.startswith("+") else "+" + contact.phone_number
    try:
        phone = parse_phone(raw)
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}", reply_markup=phone_reply_kb())
        return
    await state.update_data(phone=phone)
    await advance(message, state, ctx, "phone")


async def reply_cancel(message: Message, state: FSMContext) -> None:
    await reset_to_menu(message, state, texts.CANCELLED)


async def use_buttons(message: Message, state: FSMContext, ctx: AppContext) -> None:
    current = await state.get_state()
    if current == QuoteForm.review.state:
        await message.answer("Please use the buttons below.", reply_markup=review_kb())
    else:
        await message.answer("Please choose one of the options below.", reply_markup=freight_kb(ctx.company))


async def non_text(message: Message, state: FSMContext, ctx: AppContext) -> None:
    field = STATE_TO_FIELD.get(await state.get_state())
    markup = phone_reply_kb() if field == "phone" else (_keyboard(field, ctx) if field else review_kb())
    await message.answer("Please reply with a text message.", reply_markup=markup)


# ----------------------------------------------------------------- buttons


async def menu_quote(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await start_quote(callback, state, ctx)


async def cmd_quote(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await start_quote(message, state, ctx)


async def btn_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await reset_to_menu(callback, state, texts.CANCELLED)


async def btn_back(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    current = await state.get_state()
    data = await state.get_data()
    if current == QuoteForm.review.state or data.get("editing"):
        await state.update_data(editing=False)
        await show_review(callback, state)
        return
    field = STATE_TO_FIELD.get(current)
    index = QUOTE_STEPS.index(field) if field else 0
    await ask(callback, state, ctx, QUOTE_STEPS[max(index - 1, 0)])


async def btn_individual(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.update_data(company_name=None)
    await advance(callback, state, ctx, "company")


async def btn_date(callback: CallbackQuery, callback_data: QuoteCB, state: FSMContext, ctx: AppContext) -> None:
    today = ctx.today()
    picked: date = today if callback_data.action == "today" else today + timedelta(days=1)
    await state.update_data(pickup_date=picked.isoformat())
    await advance(callback, state, ctx, "pickup_date")


async def btn_freight(callback: CallbackQuery, callback_data: QuoteCB, state: FSMContext, ctx: AppContext) -> None:
    freight = ctx.company.freight_type(callback_data.value)
    if freight is None:
        await callback.answer("That option is no longer available.", show_alert=True)
        return
    await state.update_data(freight_type=freight.label)
    await advance(callback, state, ctx, "freight_type")


async def btn_weight_unknown(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.update_data(estimated_weight_lb=None)
    await advance(callback, state, ctx, "weight")


async def btn_skip_details(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await state.update_data(shipment_details=None)
    await advance(callback, state, ctx, "details")


async def btn_edit(callback: CallbackQuery) -> None:
    await show(callback, "✏️ <b>What would you like to change?</b>", edit_kb())


async def btn_edit_field(callback: CallbackQuery, callback_data: QuoteCB, state: FSMContext, ctx: AppContext) -> None:
    if callback_data.value not in QUOTE_STEPS:
        await callback.answer()
        return
    await state.update_data(editing=True)
    await ask(callback, state, ctx, callback_data.value)


async def btn_review(callback: CallbackQuery, state: FSMContext) -> None:
    await show_review(callback, state)


async def btn_submit(callback: CallbackQuery, state: FSMContext, ctx: AppContext, bot: Bot) -> None:
    data = await state.get_data()
    try:
        draft = QuoteDraft.model_validate({k: v for k, v in data.items() if k in DRAFT_FIELDS})
    except PydanticValidationError:
        log.warning("quote draft failed server-side validation")
        await show(callback, texts.GENERIC_ERROR + "\n\n" + texts.quote_review(data), review_kb())
        return
    if draft.pickup_date < ctx.today():
        await state.update_data(editing=True)
        await ask(callback, state, ctx, "pickup_date", prefix=f"⚠️ {texts.DATE_NOW_PAST}")
        return

    await callback.answer("Submitting…")
    review_text = texts.quote_review(data)
    if isinstance(callback.message, Message):
        # Remove the buttons while saving so the request can't be resubmitted from this screen.
        with contextlib.suppress(TelegramAPIError):
            await callback.message.edit_text(review_text + "\n\n⏳ <i>Submitting…</i>")

    try:
        result = await ctx.quotes.submit(
            telegram_user_id=callback.from_user.id,
            draft=draft,
            submission_key=data["submission_key"],
            now=ctx.now(),
            today=ctx.today(),
        )
    except QuoteRateLimited:
        await _replace(callback, review_text + "\n\n" + texts.RATE_LIMITED, review_kb())
        return
    except PickupDateInPast:
        await state.update_data(editing=True)
        await ask(callback, state, ctx, "pickup_date", prefix=f"⚠️ {texts.DATE_NOW_PAST}")
        return
    except Exception as exc:
        # Database (or any other) failure: the request was NOT saved. Never show a success message.
        log.error("quote submission failed", extra={"error": type(exc).__name__})
        await _replace(callback, review_text + "\n\n" + texts.SUBMIT_FAILED, review_kb())
        return

    await state.clear()
    await _replace(callback, texts.quote_confirmation(result.public_request_id, ctx.company), back_home_kb())
    if result.created:
        # Telegram delivery is separate from the database transaction; failures stay queued for retry.
        ctx.spawn(
            ctx.notifications.dispatch(bot, now=ctx.now(), request_id=result.request_id),
            name=f"notify:{result.public_request_id}",
        )


async def _replace(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=markup)
            return
        except TelegramAPIError:
            pass  # message too old to edit — send a new one instead
    await callback.bot.send_message(callback.from_user.id, text, reply_markup=markup)


async def stale_quote_button(callback: CallbackQuery) -> None:
    await callback.answer(
        "That button is no longer active. Use the latest message, or /start to open the menu.", show_alert=True
    )


def build_router() -> Router:
    router = Router(name="quote")
    text_states = [getattr(QuoteForm, f) for f in QUOTE_STEPS if f != "freight_type"]

    router.callback_query.register(menu_quote, MenuCB.filter(F.action == "quote"))
    router.message.register(cmd_quote, Command("quote"))

    in_form = StateFilter(QuoteForm)
    router.message.register(reply_cancel, in_form, F.text == CANCEL_TEXT)
    router.message.register(shared_contact, QuoteForm.phone, F.contact)
    router.message.register(text_answer, StateFilter(*text_states), F.text)
    router.message.register(use_buttons, StateFilter(QuoteForm.freight_type, QuoteForm.review), F.text)
    router.message.register(non_text, in_form)

    router.callback_query.register(btn_cancel, in_form, QuoteCB.filter(F.action == "cancel"))
    router.callback_query.register(btn_back, in_form, QuoteCB.filter(F.action == "back"))
    router.callback_query.register(btn_individual, QuoteForm.company, QuoteCB.filter(F.action == "individual"))
    router.callback_query.register(btn_date, QuoteForm.pickup_date, QuoteCB.filter(F.action.in_({"today", "tomorrow"})))
    router.callback_query.register(btn_freight, QuoteForm.freight_type, QuoteCB.filter(F.action == "freight"))
    router.callback_query.register(btn_weight_unknown, QuoteForm.weight, QuoteCB.filter(F.action == "weight_unknown"))
    router.callback_query.register(btn_skip_details, QuoteForm.details, QuoteCB.filter(F.action == "skip_details"))
    router.callback_query.register(btn_edit, QuoteForm.review, QuoteCB.filter(F.action == "edit"))
    router.callback_query.register(btn_edit_field, QuoteForm.review, QuoteCB.filter(F.action == "edit_field"))
    router.callback_query.register(btn_review, QuoteForm.review, QuoteCB.filter(F.action == "review"))
    router.callback_query.register(btn_submit, QuoteForm.review, QuoteCB.filter(F.action == "submit"))
    # Buttons from an earlier step or a finished form.
    router.callback_query.register(stale_quote_button, QuoteCB.filter())
    return router
