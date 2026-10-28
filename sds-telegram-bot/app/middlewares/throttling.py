from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app import texts
from app.utils.ratelimit import SlidingWindowLimiter


class ThrottlingMiddleware(BaseMiddleware):
    """Per-user flood protection for messages and button presses."""

    def __init__(self, limiter: SlidingWindowLimiter) -> None:
        self.limiter = limiter
        self.warnings = SlidingWindowLimiter(max_events=1, window_seconds=limiter.window)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None or self.limiter.hit(user.id):
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            await event.answer(texts.SLOW_DOWN, show_alert=False)
        elif isinstance(event, Message) and self.warnings.hit(user.id):
            # Stay quiet beyond one warning per burst to avoid amplifying the flood.
            await event.answer(texts.SLOW_DOWN)
        return None
