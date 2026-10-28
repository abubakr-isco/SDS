"""Administrator operations on quote requests.

Every mutating method re-checks that the acting Telegram user is an ACTIVE
administrator inside the same transaction, in addition to the router filter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import (
    Administrator,
    Customer,
    EventType,
    QuoteRequest,
    QuoteRequestEvent,
    QuoteStatus,
)
from app.database.repositories import AdminRepository, QuoteRepository


class NotAuthorized(Exception):
    pass


class RequestNotFound(Exception):
    pass


class NoChange(Exception):
    pass


@dataclass(frozen=True)
class AdminInfo:
    id: int
    telegram_user_id: int
    display_name: str


@dataclass(frozen=True)
class Stats:
    by_status: dict[QuoteStatus, int]
    total: int
    last_7_days: int
    last_30_days: int
    customers: int


class AdminService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def get_active_admin(self, telegram_user_id: int) -> AdminInfo | None:
        async with self._sessions() as session:
            admin = await AdminRepository(session).get_active(telegram_user_id)
            return _info(admin) if admin else None

    async def sync_admins(self, telegram_ids: Sequence[int]) -> None:
        """Ensure every ID from ADMIN_TELEGRAM_IDS exists and is active (startup bootstrap)."""
        if not telegram_ids:
            return
        async with self._sessions() as session, session.begin():
            repo = AdminRepository(session)
            for tid in telegram_ids:
                existing = await repo.get_by_telegram_id(tid)
                if existing is None:
                    await repo.upsert(tid)
                elif not existing.is_active:
                    existing.is_active = True

    async def list_admins(self, actor_tid: int) -> list[AdminInfo]:
        async with self._sessions() as session:
            await self._require(session, actor_tid)
            return [_info(a) for a in await AdminRepository(session).list_active()]

    async def recent(
        self, actor_tid: int, *, limit: int = 10, status: QuoteStatus | None = None
    ) -> Sequence[QuoteRequest]:
        async with self._sessions() as session:
            await self._require(session, actor_tid)
            return await QuoteRepository(session).recent(limit=limit, status=status)

    async def get(self, actor_tid: int, *, request_id: int | None = None, public_id: str | None = None) -> QuoteRequest:
        async with self._sessions() as session:
            await self._require(session, actor_tid)
            repo = QuoteRepository(session)
            request = await (repo.get(request_id) if request_id is not None else repo.get_by_public_id(public_id or ""))
            if request is None:
                raise RequestNotFound
            return request

    async def history(self, actor_tid: int, request_id: int) -> Sequence[QuoteRequestEvent]:
        async with self._sessions() as session:
            await self._require(session, actor_tid)
            return await QuoteRepository(session).events(request_id)

    async def change_status(
        self, actor_tid: int, request_id: int, new_status: QuoteStatus, note: str | None = None
    ) -> tuple[QuoteRequest, QuoteStatus]:
        async with self._sessions() as session, session.begin():
            admin = await self._require(session, actor_tid)
            repo = QuoteRepository(session)
            request = await repo.lock(request_id)
            if request is None:
                raise RequestNotFound
            previous = request.status
            if previous == new_status:
                raise NoChange
            request.status = new_status
            await repo.add_event(
                QuoteRequestEvent(
                    quote_request_id=request.id,
                    event_type=EventType.STATUS_CHANGED,
                    previous_status=previous,
                    new_status=new_status,
                    changed_by_admin_id=admin.id,
                    note=note,
                )
            )
        return await self.get(actor_tid, request_id=request_id), previous

    async def add_note(self, actor_tid: int, request_id: int, note: str) -> None:
        await self._record(actor_tid, request_id, EventType.NOTE_ADDED, note)

    async def record_customer_contact(self, actor_tid: int, request_id: int, event_type: EventType, note: str) -> None:
        await self._record(actor_tid, request_id, event_type, note)

    async def assign(self, actor_tid: int, request_id: int, assignee_admin_id: int) -> AdminInfo:
        async with self._sessions() as session, session.begin():
            admin = await self._require(session, actor_tid)
            assignee = await AdminRepository(session).get(assignee_admin_id)
            if assignee is None or not assignee.is_active:
                raise RequestNotFound
            repo = QuoteRepository(session)
            request = await repo.lock(request_id)
            if request is None:
                raise RequestNotFound
            if request.assigned_admin_id == assignee.id:
                raise NoChange
            request.assigned_admin_id = assignee.id
            await repo.add_event(
                QuoteRequestEvent(
                    quote_request_id=request.id,
                    event_type=EventType.ASSIGNED,
                    previous_status=request.status,
                    new_status=request.status,
                    changed_by_admin_id=admin.id,
                    note=f"Assigned to {assignee.display_name}",
                )
            )
            return _info(assignee)

    async def stats(self, actor_tid: int, now: datetime) -> Stats:
        async with self._sessions() as session:
            await self._require(session, actor_tid)
            repo = QuoteRepository(session)
            by_status = await repo.counts_by_status()
            return Stats(
                by_status=by_status,
                total=sum(by_status.values()),
                last_7_days=await repo.count_created_since(now - timedelta(days=7)),
                last_30_days=await repo.count_created_since(now - timedelta(days=30)),
                customers=await session.scalar(select(func.count(Customer.id))) or 0,
            )

    async def _record(self, actor_tid: int, request_id: int, event_type: EventType, note: str) -> None:
        async with self._sessions() as session, session.begin():
            admin = await self._require(session, actor_tid)
            repo = QuoteRepository(session)
            request = await repo.lock(request_id)
            if request is None:
                raise RequestNotFound
            await repo.add_event(
                QuoteRequestEvent(
                    quote_request_id=request.id,
                    event_type=event_type,
                    previous_status=request.status,
                    new_status=request.status,
                    changed_by_admin_id=admin.id,
                    note=note,
                )
            )

    @staticmethod
    async def _require(session: AsyncSession, actor_tid: int) -> Administrator:
        admin = await AdminRepository(session).get_active(actor_tid)
        if admin is None:
            raise NotAuthorized
        return admin


def _info(admin: Administrator) -> AdminInfo:
    return AdminInfo(id=admin.id, telegram_user_id=admin.telegram_user_id, display_name=admin.display_name)
