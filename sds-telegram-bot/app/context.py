"""Application context injected into every handler as `ctx`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.company import CompanyConfig
from app.config import Settings
from app.database.models import utcnow
from app.services.admin import AdminService
from app.services.notifications import NotificationService
from app.services.quotes import QuoteService
from app.services.tracking import TrackingProvider
from app.utils.ratelimit import SlidingWindowLimiter

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    settings: Settings
    company: CompanyConfig
    session_factory: async_sessionmaker[AsyncSession]
    tracking: TrackingProvider
    clock: Callable[[], datetime] = utcnow
    quotes: QuoteService = field(init=False)
    admin: AdminService = field(init=False)
    notifications: NotificationService = field(init=False)
    flood_limiter: SlidingWindowLimiter = field(init=False)
    tracking_limiter: SlidingWindowLimiter = field(init=False)
    _tasks: set[asyncio.Task] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        s = self.settings
        self.quotes = QuoteService(self.session_factory, submissions_per_hour=s.quote_submissions_per_hour)
        self.admin = AdminService(self.session_factory)
        self.notifications = NotificationService(
            self.session_factory, max_attempts=s.notification_max_attempts, tz=s.tz
        )
        self.flood_limiter = SlidingWindowLimiter(max_events=20, window_seconds=10)
        self.tracking_limiter = SlidingWindowLimiter(max_events=s.tracking_lookups_per_10_minutes, window_seconds=600)

    def now(self) -> datetime:
        return self.clock()

    def today(self) -> date:
        return self.clock().astimezone(self.settings.tz).date()

    def spawn(self, coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task:
        """Run work after replying to the user (e.g. admin notifications) without losing errors."""
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._tasks.discard(t)
            if not t.cancelled() and t.exception() is not None:
                log.error("background task failed", extra={"task": name, "error": type(t.exception()).__name__})

        task.add_done_callback(_done)
        return task

    async def drain(self) -> None:
        """Wait for background tasks (used on shutdown and in tests)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
