from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import (
    AdminNotification,
    EventType,
    NotificationStatus,
    QuoteRequest,
    QuoteRequestEvent,
    QuoteStatus,
    RequestSource,
)
from app.database.repositories import AdminRepository, CustomerRepository, QuoteRepository

log = logging.getLogger(__name__)


class QuoteDraft(BaseModel):
    """Validated contents of the quote wizard (re-validated server-side before saving)."""

    full_name: str = Field(min_length=2, max_length=100)
    company_name: str | None = Field(default=None, max_length=150)
    email: str = Field(max_length=254)
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    pickup_city: str = Field(min_length=2, max_length=80)
    pickup_state: str = Field(pattern=r"^[A-Z]{2}$")
    pickup_zip: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")
    delivery_city: str = Field(min_length=2, max_length=80)
    delivery_state: str = Field(pattern=r"^[A-Z]{2}$")
    delivery_zip: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")
    pickup_date: date
    freight_type: str = Field(min_length=1, max_length=40)
    estimated_weight_lb: int | None = Field(default=None, gt=0, le=500_000)
    shipment_details: str | None = Field(default=None, max_length=1000)
    requested_service: str | None = Field(default=None, max_length=60)


class QuoteRateLimited(Exception):
    pass


class PickupDateInPast(Exception):
    pass


@dataclass(frozen=True)
class SubmissionResult:
    request_id: int
    public_request_id: str
    created: bool  # False when this submission key was already saved (double tap / retry)


class QuoteService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        submissions_per_hour: int,
    ) -> None:
        self._sessions = session_factory
        self._per_hour = submissions_per_hour

    async def submit(
        self,
        *,
        telegram_user_id: int | None,
        draft: QuoteDraft,
        submission_key: str,
        now: datetime,
        today: date,
        source: RequestSource = RequestSource.TELEGRAM,
    ) -> SubmissionResult:
        """Save the customer, the request, its creation event and the admin notification outbox
        in a single transaction. Raises on any failure; nothing is half-saved.

        Telegram customers are identified by their Telegram user ID. Website customers
        (telegram_user_id=None) are matched by email among website-only customers.
        """
        if (telegram_user_id is None) != (source == RequestSource.WEBSITE):
            raise ValueError("website submissions have no Telegram user; Telegram submissions must have one")
        if draft.pickup_date < today:
            raise PickupDateInPast
        for attempt in range(3):
            try:
                return await self._submit_once(telegram_user_id, draft, submission_key, now, source)
            except IntegrityError:
                # Either the same submission key raced us (double tap), or two first-time
                # submissions raced on the customer row. Check, then retry.
                existing = await self._existing(submission_key, telegram_user_id, draft)
                if existing is not None:
                    return existing
                if attempt == 2:
                    raise
        raise RuntimeError("unreachable")

    async def _existing(
        self, submission_key: str, telegram_user_id: int | None, draft: QuoteDraft
    ) -> SubmissionResult | None:
        async with self._sessions() as session:
            request = await QuoteRepository(session).get_by_submission_key(submission_key)
            if request is None:
                return None
            owner = request.customer
            same_submitter = (
                owner.telegram_user_id == telegram_user_id
                if telegram_user_id is not None
                else owner.telegram_user_id is None and owner.email.lower() == draft.email.lower()
            )
            if not same_submitter:
                # A key belongs to exactly one submitter's form; never reveal another customer's request.
                raise PermissionError("submission key belongs to another submitter")
            return SubmissionResult(request.id, request.public_request_id, created=False)

    async def _submit_once(
        self,
        telegram_user_id: int | None,
        draft: QuoteDraft,
        submission_key: str,
        now: datetime,
        source: RequestSource,
    ) -> SubmissionResult:
        existing = await self._existing(submission_key, telegram_user_id, draft)
        if existing is not None:
            return existing

        async with self._sessions() as session, session.begin():
            quotes = QuoteRepository(session)
            customers = CustomerRepository(session)
            contact = dict(
                full_name=draft.full_name, company_name=draft.company_name, email=draft.email, phone=draft.phone
            )
            if telegram_user_id is not None:
                recent = await quotes.count_since(telegram_user_id, now - timedelta(hours=1))
                if recent >= self._per_hour:
                    raise QuoteRateLimited
                customer = await customers.upsert(telegram_user_id=telegram_user_id, **contact)
            else:
                # Website: rate limiting happens per client IP in the HTTP layer.
                customer = await customers.upsert_website(**contact)
            public_id = await quotes.next_public_id(now.year)
            request = QuoteRequest(
                public_request_id=public_id,
                submission_key=submission_key,
                customer_id=customer.id,
                source=source,
                requested_service=draft.requested_service,
                pickup_city=draft.pickup_city,
                pickup_state=draft.pickup_state,
                pickup_zip=draft.pickup_zip,
                delivery_city=draft.delivery_city,
                delivery_state=draft.delivery_state,
                delivery_zip=draft.delivery_zip,
                pickup_date=draft.pickup_date,
                freight_type=draft.freight_type,
                estimated_weight_lb=draft.estimated_weight_lb,
                shipment_details=draft.shipment_details,
                status=QuoteStatus.NEW,
            )
            session.add(request)
            await session.flush()
            await quotes.add_event(
                QuoteRequestEvent(
                    quote_request_id=request.id,
                    event_type=EventType.CREATED,
                    previous_status=None,
                    new_status=QuoteStatus.NEW,
                )
            )
            # Transactional outbox: notifications exist if and only if the request exists.
            for admin in await AdminRepository(session).list_active():
                session.add(
                    AdminNotification(
                        quote_request_id=request.id, administrator_id=admin.id, status=NotificationStatus.PENDING
                    )
                )
            await session.flush()
            result = SubmissionResult(request.id, public_id, created=True)
        log.info("quote request saved", extra={"request_id": public_id, "source": source.value})
        return result

    async def status_for_customer(self, public_id: str, telegram_user_id: int) -> QuoteRequest | None:
        async with self._sessions() as session:
            return await QuoteRepository(session).get_for_customer(public_id, telegram_user_id)
