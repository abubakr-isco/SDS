from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Administrator, AdminNotification, NotificationStatus, QuoteRequest


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def due(
        self, *, max_attempts: int, stale_before: datetime, request_id: int | None = None, limit: int = 50
    ) -> Sequence[AdminNotification]:
        """Notifications that should be (re)sent.

        Includes rows stuck in SENDING (process died mid-send) once they are older than `stale_before`.
        """
        query = (
            select(AdminNotification)
            .join(Administrator)
            .options(
                selectinload(AdminNotification.administrator),
                selectinload(AdminNotification.quote_request).selectinload(QuoteRequest.customer),
            )
            .where(
                Administrator.is_active.is_(True),
                AdminNotification.attempts < max_attempts,
                or_(
                    AdminNotification.status.in_([NotificationStatus.PENDING, NotificationStatus.FAILED]),
                    and_(
                        AdminNotification.status == NotificationStatus.SENDING,
                        AdminNotification.updated_at < stale_before,
                    ),
                ),
            )
            .order_by(AdminNotification.id)
            .limit(limit)
        )
        if request_id is not None:
            query = query.where(AdminNotification.quote_request_id == request_id)
        return (await self.session.scalars(query)).all()

    async def claim(self, notification_id: int, *, now: datetime, stale_before: datetime) -> bool:
        """Atomically move a notification to SENDING. Only one worker can win, so nothing is sent twice."""
        result = await self.session.execute(
            update(AdminNotification)
            .where(
                AdminNotification.id == notification_id,
                or_(
                    AdminNotification.status.in_([NotificationStatus.PENDING, NotificationStatus.FAILED]),
                    and_(
                        AdminNotification.status == NotificationStatus.SENDING,
                        AdminNotification.updated_at < stale_before,
                    ),
                ),
            )
            .values(
                status=NotificationStatus.SENDING,
                attempts=AdminNotification.attempts + 1,
                updated_at=now,
            )
        )
        return result.rowcount == 1

    async def mark(
        self, notification_id: int, status: NotificationStatus, *, now: datetime, error: str | None = None
    ) -> None:
        values: dict[str, object] = {"status": status, "last_error": error, "updated_at": now}
        if status == NotificationStatus.SENT:
            values["sent_at"] = now
        await self.session.execute(
            update(AdminNotification).where(AdminNotification.id == notification_id).values(**values)
        )

    async def for_request(self, request_id: int) -> Sequence[AdminNotification]:
        return (
            await self.session.scalars(
                select(AdminNotification)
                .where(AdminNotification.quote_request_id == request_id)
                .order_by(AdminNotification.id)
            )
        ).all()
