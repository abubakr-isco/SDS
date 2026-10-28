"""Administrator notifications for new quote requests (transactional outbox delivery)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import AdminNotification, NotificationStatus
from app.database.repositories import NotificationRepository
from app.keyboards.admin import open_request_kb
from app.texts import admin_new_request_text

log = logging.getLogger(__name__)

STALE_SENDING = timedelta(minutes=5)


@dataclass
class DispatchReport:
    sent: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def telegram_error_code(exc: Exception) -> str:
    """Short, non-sensitive description of a Telegram delivery failure."""
    if isinstance(exc, TelegramForbiddenError):
        return "forbidden"  # user blocked the bot or never started it
    if isinstance(exc, TelegramRetryAfter):
        return "rate_limited"
    if isinstance(exc, TelegramBadRequest):
        return "bad_request"
    if isinstance(exc, TelegramNetworkError):
        return "network"
    if isinstance(exc, TelegramAPIError):
        return "telegram_api"
    return type(exc).__name__[:100]


class NotificationService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], *, max_attempts: int, tz) -> None:
        self._sessions = session_factory
        self._max_attempts = max_attempts
        self._tz = tz

    async def dispatch(self, bot: Bot, *, now: datetime, request_id: int | None = None) -> DispatchReport:
        """Send due notifications. Each one is claimed atomically before sending, so concurrent
        dispatchers (immediate send + retry loop) never deliver the same notification twice."""
        report = DispatchReport()
        stale_before = now - STALE_SENDING
        async with self._sessions() as session:
            due = await NotificationRepository(session).due(
                max_attempts=self._max_attempts, stale_before=stale_before, request_id=request_id
            )
        for notification in due:
            await self._deliver(bot, notification, now, report)
        if report.sent or report.failed:
            log.info("admin notifications dispatched", extra={"sent": report.sent, "failed": report.failed})
        return report

    async def _deliver(self, bot: Bot, notification: AdminNotification, now: datetime, report: DispatchReport) -> None:
        async with self._sessions() as session, session.begin():
            if not await NotificationRepository(session).claim(
                notification.id, now=now, stale_before=now - STALE_SENDING
            ):
                return  # another dispatcher took it
        request = notification.quote_request
        try:
            await bot.send_message(
                notification.administrator.telegram_user_id,
                admin_new_request_text(request, request.customer, self._tz),
                reply_markup=open_request_kb(request.id),
            )
        except Exception as exc:  # Telegram errors are handled separately from database errors
            code = telegram_error_code(exc)
            report.failed += 1
            report.errors.append(code)
            log.warning(
                "admin notification failed",
                extra={"request_id": request.public_request_id, "notification_id": notification.id, "error": code},
            )
            async with self._sessions() as session, session.begin():
                await NotificationRepository(session).mark(
                    notification.id, NotificationStatus.FAILED, now=now, error=code
                )
            if isinstance(exc, TelegramRetryAfter):
                await asyncio.sleep(min(exc.retry_after, 30))
            return
        report.sent += 1
        async with self._sessions() as session, session.begin():
            await NotificationRepository(session).mark(notification.id, NotificationStatus.SENT, now=now)
