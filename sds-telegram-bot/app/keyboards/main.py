from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.company import CompanyConfig, ContactInfo
from app.keyboards.callbacks import MenuCB, ServiceCB


def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚛 Our Services", callback_data=MenuCB(action="services"))
    b.button(text="📋 Request a Freight Quote", callback_data=MenuCB(action="quote"))
    b.button(text="📍 Track a Shipment", callback_data=MenuCB(action="track"))
    b.button(text="☎️ Contact SDS", callback_data=MenuCB(action="contact"))
    b.button(text="ℹ️ About SDS", callback_data=MenuCB(action="about"))
    b.adjust(1, 1, 2, 1)
    return b.as_markup()


def home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="🏠 Main Menu", callback_data=MenuCB(action="home").pack())


def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[home_button()]])


def services_kb(company: CompanyConfig, *, development: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    shown = company.services if development else company.enabled_services
    for service in shown:
        b.button(text=f"📋 Request a Quote — {service.name}", callback_data=ServiceCB(key=service.key))
    b.button(text="📋 Request a Freight Quote", callback_data=MenuCB(action="quote"))
    b.button(text="☎️ Contact SDS", callback_data=MenuCB(action="contact"))
    b.adjust(*([1] * len(shown)), 1, 1)
    b.row(home_button())
    return b.as_markup()


def contact_kb(info: ContactInfo) -> InlineKeyboardMarkup:
    # Telegram URL buttons accept http(s)/tg links only, so phone and email are shown as text
    # (Telegram makes them tappable automatically).
    rows: list[list[InlineKeyboardButton]] = []
    if info.website:
        rows.append([InlineKeyboardButton(text="🌐 Visit our website", url=str(info.website))])
    rows.append([InlineKeyboardButton(text="📋 Request a Freight Quote", callback_data=MenuCB(action="quote").pack())])
    rows.append([home_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def about_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚛 Our Services", callback_data=MenuCB(action="services"))
    b.button(text="📋 Request a Freight Quote", callback_data=MenuCB(action="quote"))
    b.adjust(2)
    b.row(home_button())
    return b.as_markup()
