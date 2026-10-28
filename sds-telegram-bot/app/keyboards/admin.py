from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import QuoteRequest, QuoteStatus
from app.keyboards.callbacks import AdminCB


def open_request_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Open request", callback_data=AdminCB(action="view", rid=request_id).pack())]
        ]
    )


def dashboard_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🆕 New requests", callback_data=AdminCB(action="list", value=QuoteStatus.NEW.value))
    b.button(text="📥 Recent requests", callback_data=AdminCB(action="list"))
    b.button(text="📊 Statistics", callback_data=AdminCB(action="stats"))
    b.button(text="🔁 Retry notifications", callback_data=AdminCB(action="retry"))
    b.adjust(2, 2)
    return b.as_markup()


def request_list_kb(requests: Sequence[QuoteRequest]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in requests:
        b.button(
            text=f"{r.public_request_id} · {r.status.label} · {r.pickup_state}→{r.delivery_state}",
            callback_data=AdminCB(action="view", rid=r.id),
        )
    b.button(text="⬅️ Dashboard", callback_data=AdminCB(action="dash"))
    b.adjust(1)
    return b.as_markup()


def request_kb(request_id: int, *, can_message: bool = True) -> InlineKeyboardMarkup:
    """`can_message` is False for website customers, who can't be reached through Telegram."""
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Change status", callback_data=AdminCB(action="status_menu", rid=request_id))
    b.button(text="📝 Add note", callback_data=AdminCB(action="note", rid=request_id))
    b.button(text="👤 Assign", callback_data=AdminCB(action="assign_menu", rid=request_id))
    if can_message:
        b.button(text="✉️ Message customer", callback_data=AdminCB(action="message", rid=request_id))
    b.button(text="🗂 History", callback_data=AdminCB(action="history", rid=request_id))
    b.button(text="⬅️ Requests", callback_data=AdminCB(action="list"))
    b.adjust(2, 2, 2)
    return b.as_markup()


def status_menu_kb(request_id: int, current: QuoteStatus) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for status in QuoteStatus:
        if status != current:
            b.button(text=status.label, callback_data=AdminCB(action="set_status", rid=request_id, value=status.value))
    b.button(text="⬅️ Back", callback_data=AdminCB(action="view", rid=request_id))
    b.adjust(2)
    return b.as_markup()


def status_confirm_kb(request_id: int, status: QuoteStatus, *, can_notify: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if can_notify:
        b.button(
            text="✅ Save & notify customer",
            callback_data=AdminCB(action="apply_status", rid=request_id, value=f"{status.value}|1"),
        )
    b.button(
        text="💾 Save without notifying" if can_notify else "💾 Save",
        callback_data=AdminCB(action="apply_status", rid=request_id, value=f"{status.value}|0"),
    )
    b.button(text="⬅️ Back", callback_data=AdminCB(action="status_menu", rid=request_id))
    b.adjust(1)
    return b.as_markup()


def assign_kb(request_id: int, admins: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for admin_id, name in admins:
        b.button(text=name, callback_data=AdminCB(action="assign", rid=request_id, value=str(admin_id)))
    b.button(text="⬅️ Back", callback_data=AdminCB(action="view", rid=request_id))
    b.adjust(1)
    return b.as_markup()


def back_to_request_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Back to request", callback_data=AdminCB(action="view", rid=request_id).pack()
                )
            ]
        ]
    )


def cancel_input_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data=AdminCB(action="view", rid=request_id).pack())]
        ]
    )
