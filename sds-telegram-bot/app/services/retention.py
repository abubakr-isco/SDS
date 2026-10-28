"""Customer data retention: delete closed requests (and orphaned customers) after N days."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import CLOSED_STATUSES
from app.database.repositories import QuoteRepository

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurgeResult:
    requests: int
    customers: int


async def purge_expired(
    session_factory: async_sessionmaker[AsyncSession], *, retention_days: int, now: datetime, dry_run: bool = False
) -> PurgeResult:
    if retention_days <= 0:
        return PurgeResult(0, 0)
    cutoff = now - timedelta(days=retention_days)
    async with session_factory() as session:
        repo = QuoteRepository(session)
        requests = await repo.purge_closed_before(cutoff, CLOSED_STATUSES)
        customers = await repo.purge_customers_without_requests(cutoff)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    log.info(
        "retention purge",
        extra={"requests": requests, "customers": customers, "dry_run": dry_run, "days": retention_days},
    )
    return PurgeResult(requests, customers)
