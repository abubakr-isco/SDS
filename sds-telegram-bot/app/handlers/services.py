from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app import texts
from app.context import AppContext
from app.handlers.common import show
from app.handlers.quote import start_quote
from app.keyboards.callbacks import MenuCB, ServiceCB
from app.keyboards.main import services_kb


async def menu_services(callback: CallbackQuery, ctx: AppContext) -> None:
    dev = ctx.settings.is_development
    await show(callback, texts.services(ctx.company, development=dev), services_kb(ctx.company, development=dev))


async def quote_for_service(
    callback: CallbackQuery, callback_data: ServiceCB, state: FSMContext, ctx: AppContext
) -> None:
    service = ctx.company.service(callback_data.key)
    # Never start a quote for a service that is not enabled (stale or forged button) in production.
    if service is None or (not service.enabled and not ctx.settings.is_development):
        await callback.answer("This service isn't available right now. Please contact SDS.", show_alert=True)
        return
    await start_quote(callback, state, ctx, service_name=service.name)


def build_router() -> Router:
    router = Router(name="services")
    router.callback_query.register(menu_services, MenuCB.filter(F.action == "services"))
    router.callback_query.register(quote_for_service, ServiceCB.filter())
    return router
