from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Customer,
    QuoteRequest,
    QuoteRequestCounter,
    QuoteRequestEvent,
    QuoteStatus,
)


class QuoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_public_id(self, year: int) -> str:
        """Allocate the next ID for the year atomically (row lock on the counter).

        Runs inside the caller's transaction, so a failed submission rolls the
        counter back with it. The UNIQUE constraint on public_request_id is the
        final guard against collisions.
        """
        insert = pg_insert if self.session.bind.dialect.name == "postgresql" else sqlite_insert
        await self.session.execute(
            insert(QuoteRequestCounter).values(year=year, last_value=0).on_conflict_do_nothing(index_elements=["year"])
        )
        value = await self.session.scalar(
            update(QuoteRequestCounter)
            .where(QuoteRequestCounter.year == year)
            .values(last_value=QuoteRequestCounter.last_value + 1)
            .returning(QuoteRequestCounter.last_value)
        )
        return f"SDS-Q-{year}-{value:04d}"

    async def get_by_submission_key(self, key: str) -> QuoteRequest | None:
        return await self.session.scalar(
            select(QuoteRequest).options(selectinload(QuoteRequest.customer)).where(QuoteRequest.submission_key == key)
        )

    async def get(self, request_id: int) -> QuoteRequest | None:
        return await self.session.scalar(
            select(QuoteRequest)
            .options(selectinload(QuoteRequest.customer), selectinload(QuoteRequest.assigned_admin))
            .where(QuoteRequest.id == request_id)
        )

    async def get_by_public_id(self, public_id: str) -> QuoteRequest | None:
        return await self.session.scalar(
            select(QuoteRequest)
            .options(selectinload(QuoteRequest.customer), selectinload(QuoteRequest.assigned_admin))
            .where(QuoteRequest.public_request_id == public_id.upper())
        )

    async def get_for_customer(self, public_id: str, telegram_user_id: int) -> QuoteRequest | None:
        """Only returns the request if it belongs to this Telegram user."""
        return await self.session.scalar(
            select(QuoteRequest)
            .join(Customer)
            .where(QuoteRequest.public_request_id == public_id.upper(), Customer.telegram_user_id == telegram_user_id)
        )

    async def lock(self, request_id: int) -> QuoteRequest | None:
        return await self.session.scalar(select(QuoteRequest).where(QuoteRequest.id == request_id).with_for_update())

    async def recent(self, limit: int = 10, status: QuoteStatus | None = None) -> Sequence[QuoteRequest]:
        query = select(QuoteRequest).options(selectinload(QuoteRequest.customer))
        if status is not None:
            query = query.where(QuoteRequest.status == status)
        query = query.order_by(QuoteRequest.created_at.desc(), QuoteRequest.id.desc()).limit(limit)
        return (await self.session.scalars(query)).all()

    async def count_since(self, telegram_user_id: int, since: datetime) -> int:
        return (
            await self.session.scalar(
                select(func.count(QuoteRequest.id))
                .join(Customer)
                .where(Customer.telegram_user_id == telegram_user_id, QuoteRequest.created_at >= since)
            )
            or 0
        )

    async def add_event(self, event: QuoteRequestEvent) -> None:
        self.session.add(event)
        await self.session.flush()

    async def events(self, request_id: int, limit: int = 20) -> Sequence[QuoteRequestEvent]:
        query = (
            select(QuoteRequestEvent)
            .options(selectinload(QuoteRequestEvent.changed_by))
            .where(QuoteRequestEvent.quote_request_id == request_id)
            .order_by(QuoteRequestEvent.id.desc())
            .limit(limit)
        )
        return list(reversed((await self.session.scalars(query)).all()))

    async def counts_by_status(self) -> dict[QuoteStatus, int]:
        rows = await self.session.execute(
            select(QuoteRequest.status, func.count(QuoteRequest.id)).group_by(QuoteRequest.status)
        )
        return {QuoteStatus(status): count for status, count in rows.all()}

    async def count_created_since(self, since: datetime) -> int:
        return (
            await self.session.scalar(select(func.count(QuoteRequest.id)).where(QuoteRequest.created_at >= since)) or 0
        )

    async def purge_closed_before(self, cutoff: datetime, closed: Sequence[QuoteStatus]) -> int:
        result = await self.session.execute(
            delete(QuoteRequest).where(QuoteRequest.status.in_(closed), QuoteRequest.updated_at < cutoff)
        )
        return result.rowcount or 0

    async def purge_customers_without_requests(self, cutoff: datetime) -> int:
        has_request = select(QuoteRequest.id).where(QuoteRequest.customer_id == Customer.id).exists()
        result = await self.session.execute(delete(Customer).where(~has_request, Customer.updated_at < cutoff))
        return result.rowcount or 0
