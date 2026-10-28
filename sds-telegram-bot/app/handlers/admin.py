"""Administrator interface.

Authorization is enforced twice: the IsAdmin filter on every update reaching
this router, and AdminService re-checking inside each database transaction.
"""

from __future__ import annotations

import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from app import texts
from app.context import AppContext
from app.database.models import EventType, QuoteStatus
from app.handlers.common import show
from app.keyboards.admin import (
    assign_kb,
    back_to_request_kb,
    cancel_input_kb,
    dashboard_kb,
    request_kb,
    request_list_kb,
    status_confirm_kb,
    status_menu_kb,
)
from app.keyboards.callbacks import AdminCB
from app.services.admin import AdminInfo, NoChange, NotAuthorized, RequestNotFound
from app.services.notifications import telegram_error_code
from app.states import AdminInput
from app.utils.validation import clean_text

log = logging.getLogger(__name__)

PUBLIC_ID = re.compile(r"^SDS-Q-\d{4}-\d{4,}$", re.IGNORECASE)
MAX_NOTE = 1000


class IsAdmin(Filter):
    """Passes only for active administrators; injects `admin: AdminInfo` into the handler."""

    async def __call__(self, event: TelegramObject, ctx: AppContext) -> bool | dict:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        admin = await ctx.admin.get_active_admin(user.id)
        return {"admin": admin} if admin else False


def _request_kb(request) -> InlineKeyboardMarkup:
    return request_kb(request.id, can_message=request.customer.telegram_user_id is not None)


# ----------------------------------------------------------------- commands


async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.ADMIN_DASHBOARD, reply_markup=dashboard_kb())


async def cmd_requests(message: Message, command: CommandObject, admin: AdminInfo, ctx: AppContext) -> None:
    status = None
    if command.args:
        try:
            status = QuoteStatus(command.args.strip().lower())
        except ValueError:
            await message.answer("Unknown status. Use one of: " + ", ".join(s.value for s in QuoteStatus))
            return
    await _send_list(message, admin, ctx, status)


async def cmd_request(message: Message, command: CommandObject, admin: AdminInfo, ctx: AppContext) -> None:
    public_id = (command.args or "").strip()
    if not PUBLIC_ID.fullmatch(public_id):
        await message.answer("Usage: /request SDS-Q-2026-0001")
        return
    try:
        request = await ctx.admin.get(admin.telegram_user_id, public_id=public_id)
    except RequestNotFound:
        await message.answer(f"Request {public_id.upper()} was not found.")
        return
    await message.answer(texts.admin_request_card(request, ctx.settings.tz), reply_markup=_request_kb(request))


async def cmd_stats(message: Message, admin: AdminInfo, ctx: AppContext) -> None:
    stats = await ctx.admin.stats(admin.telegram_user_id, ctx.now())
    await message.answer(texts.admin_stats(stats), reply_markup=dashboard_kb())


# ----------------------------------------------------------------- dashboard callbacks


async def cb_dashboard(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show(callback, texts.ADMIN_DASHBOARD, dashboard_kb())


async def cb_list(
    callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext, state: FSMContext
) -> None:
    await state.clear()
    status = QuoteStatus(callback_data.value) if callback_data.value else None
    await _send_list(callback, admin, ctx, status)


async def cb_stats(callback: CallbackQuery, admin: AdminInfo, ctx: AppContext) -> None:
    stats = await ctx.admin.stats(admin.telegram_user_id, ctx.now())
    await show(callback, texts.admin_stats(stats), dashboard_kb())


async def cb_retry(callback: CallbackQuery, ctx: AppContext, bot: Bot) -> None:
    await callback.answer("Retrying pending notifications…")
    report = await ctx.notifications.dispatch(bot, now=ctx.now())
    await show(callback, f"🔁 Notifications retried.\nSent: {report.sent} · Failed: {report.failed}", dashboard_kb())


async def _send_list(
    event: Message | CallbackQuery, admin: AdminInfo, ctx: AppContext, status: QuoteStatus | None
) -> None:
    requests = await ctx.admin.recent(admin.telegram_user_id, limit=10, status=status)
    title = f"🆕 <b>{status.label} requests</b>" if status else "📥 <b>Recent requests</b>"
    if not requests:
        await show(event, f"{title}\n\nNo requests found.", request_list_kb([]))
        return
    await show(event, f"{title}\n\nTap a request to open it.", request_list_kb(requests))


# ----------------------------------------------------------------- request callbacks


async def cb_view(
    callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext, state: FSMContext
) -> None:
    await state.clear()
    try:
        request = await ctx.admin.get(admin.telegram_user_id, request_id=callback_data.rid)
    except RequestNotFound:
        await callback.answer("Request not found.", show_alert=True)
        return
    await show(callback, texts.admin_request_card(request, ctx.settings.tz), _request_kb(request))


async def cb_status_menu(callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext) -> None:
    try:
        request = await ctx.admin.get(admin.telegram_user_id, request_id=callback_data.rid)
    except RequestNotFound:
        await callback.answer("Request not found.", show_alert=True)
        return
    await show(
        callback,
        f"🔄 <b>{request.public_request_id}</b>\nCurrent status: <b>{request.status.label}</b>\n\nChoose the new status:",
        status_menu_kb(request.id, request.status),
    )


async def cb_set_status(callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext) -> None:
    try:
        status = QuoteStatus(callback_data.value)
    except ValueError:
        await callback.answer("Unknown status.", show_alert=True)
        return
    try:
        request = await ctx.admin.get(admin.telegram_user_id, request_id=callback_data.rid)
    except RequestNotFound:
        await callback.answer("Request not found.", show_alert=True)
        return
    on_telegram = request.customer.telegram_user_id is not None
    detail = (
        f"If you notify the customer, they will receive:\n<i>{texts.CUSTOMER_STATUS_NOTES[status]}</i>"
        if on_telegram
        else texts.WEBSITE_CUSTOMER_NOTE
    )
    await show(
        callback,
        f"Change status to <b>{status.label}</b>?\n\n{detail}",
        status_confirm_kb(callback_data.rid, status, can_notify=on_telegram),
    )


async def cb_apply_status(
    callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext, bot: Bot
) -> None:
    raw_status, _, notify_flag = callback_data.value.partition("|")
    try:
        status = QuoteStatus(raw_status)
    except ValueError:
        await callback.answer("Unknown status.", show_alert=True)
        return
    try:
        request, previous = await ctx.admin.change_status(admin.telegram_user_id, callback_data.rid, status)
    except NoChange:
        await callback.answer("The request already has that status.", show_alert=True)
        return
    except RequestNotFound:
        await callback.answer("Request not found.", show_alert=True)
        return
    log.info(
        "status changed",
        extra={
            "request_id": request.public_request_id,
            "from": previous.value,
            "to": status.value,
            "admin_id": admin.id,
        },
    )
    result = f"✅ Status changed: {previous.label} → {status.label}."
    if notify_flag == "1" and request.customer.telegram_user_id is None:
        result += "\n⚠️ Website customer — not notified. Contact them by phone or email."
    elif notify_flag == "1":
        try:
            await bot.send_message(request.customer.telegram_user_id, texts.customer_status_update(request))
        except Exception as exc:
            result += (
                f"\n⚠️ The customer could not be notified ({telegram_error_code(exc)}). The status change is saved."
            )
        else:
            await ctx.admin.record_customer_contact(
                admin.telegram_user_id, request.id, EventType.CUSTOMER_NOTIFIED, f"Status update sent: {status.label}"
            )
            result += "\n📨 Customer notified."
    await show(callback, result + "\n\n" + texts.admin_request_card(request, ctx.settings.tz), _request_kb(request))


async def cb_history(callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext) -> None:
    try:
        request = await ctx.admin.get(admin.telegram_user_id, request_id=callback_data.rid)
    except RequestNotFound:
        await callback.answer("Request not found.", show_alert=True)
        return
    events = await ctx.admin.history(admin.telegram_user_id, request.id)
    await show(
        callback,
        texts.admin_history(request.public_request_id, events, ctx.settings.tz),
        back_to_request_kb(request.id),
    )


async def cb_assign_menu(callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext) -> None:
    admins = await ctx.admin.list_admins(admin.telegram_user_id)
    options = [(a.id, ("👤 Me — " if a.id == admin.id else "") + a.display_name) for a in admins]
    await show(callback, "👤 <b>Assign this request to:</b>", assign_kb(callback_data.rid, options))


async def cb_assign(callback: CallbackQuery, callback_data: AdminCB, admin: AdminInfo, ctx: AppContext) -> None:
    try:
        assignee = await ctx.admin.assign(admin.telegram_user_id, callback_data.rid, int(callback_data.value))
    except NoChange:
        await callback.answer("Already assigned to that administrator.", show_alert=True)
        return
    except (RequestNotFound, ValueError):
        await callback.answer("Request or administrator not found.", show_alert=True)
        return
    request = await ctx.admin.get(admin.telegram_user_id, request_id=callback_data.rid)
    await show(
        callback,
        f"✅ Assigned to {assignee.display_name}.\n\n" + texts.admin_request_card(request, ctx.settings.tz),
        _request_kb(request),
    )


async def cb_note(callback: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    await state.set_state(AdminInput.note)
    await state.update_data(rid=callback_data.rid)
    await show(callback, "📝 Send the internal note (customers never see notes).", cancel_input_kb(callback_data.rid))


async def cb_message(
    callback: CallbackQuery, callback_data: AdminCB, state: FSMContext, admin: AdminInfo, ctx: AppContext
) -> None:
    try:
        request = await ctx.admin.get(admin.telegram_user_id, request_id=callback_data.rid)
    except RequestNotFound:
        await callback.answer("Request not found.", show_alert=True)
        return
    if request.customer.telegram_user_id is None:
        await callback.answer("This customer used the website form — contact them by phone or email.", show_alert=True)
        return
    await state.set_state(AdminInput.message)
    await state.update_data(rid=callback_data.rid)
    await show(
        callback,
        "✉️ Send the message for the customer. It will be delivered by the bot as a message from SDS.",
        cancel_input_kb(callback_data.rid),
    )


async def input_note(message: Message, state: FSMContext, admin: AdminInfo, ctx: AppContext) -> None:
    rid = (await state.get_data()).get("rid")
    note = clean_text(message.text or "")
    if not note or len(note) > MAX_NOTE:
        await message.answer(
            f"Please send a note between 1 and {MAX_NOTE} characters.", reply_markup=cancel_input_kb(rid)
        )
        return
    await state.clear()
    try:
        await ctx.admin.add_note(admin.telegram_user_id, rid, note)
    except RequestNotFound:
        await message.answer("Request not found.")
        return
    await message.answer("📝 Note saved.", reply_markup=back_to_request_kb(rid))


async def input_message(message: Message, state: FSMContext, admin: AdminInfo, ctx: AppContext, bot: Bot) -> None:
    rid = (await state.get_data()).get("rid")
    text = (message.text or "").strip()
    if not text or len(text) > MAX_NOTE:
        await message.answer(
            f"Please send a message between 1 and {MAX_NOTE} characters.", reply_markup=cancel_input_kb(rid)
        )
        return
    await state.clear()
    try:
        request = await ctx.admin.get(admin.telegram_user_id, request_id=rid)
    except RequestNotFound:
        await message.answer("Request not found.")
        return
    try:
        await bot.send_message(request.customer.telegram_user_id, texts.customer_message(request, text))
    except Exception as exc:
        await message.answer(
            f"⚠️ The message was not delivered ({telegram_error_code(exc)}).", reply_markup=back_to_request_kb(rid)
        )
        return
    await ctx.admin.record_customer_contact(admin.telegram_user_id, rid, EventType.CUSTOMER_MESSAGED, text)
    await message.answer("📨 Message delivered to the customer.", reply_markup=back_to_request_kb(rid))


async def input_not_text(message: Message, state: FSMContext) -> None:
    rid = (await state.get_data()).get("rid")
    await message.answer("Please send text, or tap Cancel.", reply_markup=cancel_input_kb(rid))


# ----------------------------------------------------------------- non-admins


async def deny_command(message: Message) -> None:
    await message.answer(texts.NOT_AUTHORIZED)


async def deny_callback(callback: CallbackQuery) -> None:
    await callback.answer(texts.NOT_AUTHORIZED, show_alert=True)


async def deny_input(message: Message, state: FSMContext) -> None:
    # The user lost admin rights while typing a note/message.
    await state.clear()
    await message.answer(texts.NOT_AUTHORIZED)


ADMIN_COMMANDS = ("admin", "requests", "request", "stats")


def build_router() -> Router:
    router = Router(name="admin")
    # IsAdmin is the LAST filter on every handler: cheap command/callback filters run first, so ordinary
    # customer messages never trigger an admin lookup, while every admin action is re-authorized.
    is_admin = IsAdmin()

    msg = router.message.register
    msg(cmd_admin, Command("admin"), is_admin)
    msg(cmd_requests, Command("requests"), is_admin)
    msg(cmd_request, Command("request"), is_admin)
    msg(cmd_stats, Command("stats"), is_admin)
    msg(input_note, AdminInput.note, F.text, is_admin)
    msg(input_message, AdminInput.message, F.text, is_admin)
    msg(input_not_text, StateFilter(AdminInput), is_admin)

    cb = router.callback_query.register
    for action, handler in {
        "dash": cb_dashboard,
        "list": cb_list,
        "stats": cb_stats,
        "retry": cb_retry,
        "view": cb_view,
        "status_menu": cb_status_menu,
        "set_status": cb_set_status,
        "apply_status": cb_apply_status,
        "history": cb_history,
        "assign_menu": cb_assign_menu,
        "assign": cb_assign,
        "note": cb_note,
        "message": cb_message,
    }.items():
        cb(handler, AdminCB.filter(F.action == action), is_admin)
    return router


def build_denied_router() -> Router:
    """Catches admin commands/buttons from everyone the IsAdmin filter rejected."""
    router = Router(name="admin_denied")
    router.message.register(deny_command, Command(*ADMIN_COMMANDS))
    router.message.register(deny_input, StateFilter(AdminInput))
    router.callback_query.register(deny_callback, AdminCB.filter())
    return router


__all__ = ["IsAdmin", "NotAuthorized", "build_denied_router", "build_router"]
