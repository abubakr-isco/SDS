from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="m"):
    action: str  # home | services | quote | track | contact | about


class ServiceCB(CallbackData, prefix="svc"):
    key: str


class QuoteCB(CallbackData, prefix="q"):
    action: str  # cancel | back | individual | today | tomorrow | freight | weight_unknown | skip_details
    #             | submit | edit | edit_field | review
    value: str = ""


class AdminCB(CallbackData, prefix="a"):
    action: str
    rid: int = 0
    value: str = ""
