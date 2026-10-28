from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.company import CompanyConfig
from app.keyboards.callbacks import QuoteCB

CANCEL_TEXT = "❌ Cancel"
SHARE_PHONE_TEXT = "📱 Share my phone number"


def _nav(b: InlineKeyboardBuilder, *, back: bool = True) -> None:
    row = []
    if back:
        row.append(InlineKeyboardButton(text="⬅️ Back", callback_data=QuoteCB(action="back").pack()))
    row.append(InlineKeyboardButton(text="❌ Cancel", callback_data=QuoteCB(action="cancel").pack()))
    b.row(*row)


def step_kb(*, back: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _nav(b, back=back)
    return b.as_markup()


def company_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Individual / Not applicable", callback_data=QuoteCB(action="individual"))
    _nav(b)
    return b.as_markup()


def phone_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SHARE_PHONE_TEXT, request_contact=True)], [KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="+1 215 555 0123",
    )


def date_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Today", callback_data=QuoteCB(action="today"))
    b.button(text="Tomorrow", callback_data=QuoteCB(action="tomorrow"))
    b.adjust(2)
    _nav(b)
    return b.as_markup()


def freight_kb(company: CompanyConfig) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ft in company.enabled_freight_types:
        b.button(text=ft.label, callback_data=QuoteCB(action="freight", value=ft.key))
    b.adjust(1)
    _nav(b)
    return b.as_markup()


def weight_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Not sure / Unknown", callback_data=QuoteCB(action="weight_unknown"))
    _nav(b)
    return b.as_markup()


def details_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Skip — no additional details", callback_data=QuoteCB(action="skip_details"))
    _nav(b)
    return b.as_markup()


def review_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Submit Request", callback_data=QuoteCB(action="submit"))
    b.button(text="✏️ Edit Information", callback_data=QuoteCB(action="edit"))
    b.button(text="❌ Cancel", callback_data=QuoteCB(action="cancel"))
    b.adjust(1)
    return b.as_markup()


EDITABLE_FIELDS: list[tuple[str, str]] = [
    ("full_name", "Name"),
    ("company", "Company"),
    ("email", "Email"),
    ("phone", "Phone"),
    ("pickup", "Pickup location"),
    ("delivery", "Delivery location"),
    ("pickup_date", "Pickup date"),
    ("freight_type", "Freight type"),
    ("weight", "Weight"),
    ("details", "Shipment details"),
]


def edit_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in EDITABLE_FIELDS:
        b.button(text=label, callback_data=QuoteCB(action="edit_field", value=key))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Back to review", callback_data=QuoteCB(action="review").pack()))
    return b.as_markup()
