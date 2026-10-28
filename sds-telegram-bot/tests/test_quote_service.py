import asyncio
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.database.models import Customer, QuoteRequest
from app.services.quotes import PickupDateInPast, QuoteDraft, QuoteService
from tests.conftest import CUSTOMER_ID, FIXED_NOW

DRAFT = dict(
    full_name="Jane Carter",
    company_name=None,
    email="jane@acme.com",
    phone="+12155550123",
    pickup_city="Dallas",
    pickup_state="TX",
    delivery_city="Atlanta",
    delivery_state="GA",
    pickup_date=date(2026, 11, 4),
    freight_type="General Freight",
)
TODAY = date(2026, 10, 28)


def service(session_factory, per_hour=100) -> QuoteService:
    return QuoteService(session_factory, submissions_per_hour=per_hour)


async def submit(svc, user_id=CUSTOMER_ID, key=None, now: datetime = FIXED_NOW, **overrides):
    return await svc.submit(
        telegram_user_id=user_id,
        draft=QuoteDraft(**{**DRAFT, **overrides}),
        submission_key=key or str(uuid.uuid4()),
        now=now,
        today=TODAY,
    )


async def test_ids_are_sequential_per_year(session_factory):
    svc = service(session_factory)
    ids = [(await submit(svc)).public_request_id for _ in range(3)]
    assert ids == ["SDS-Q-2026-0001", "SDS-Q-2026-0002", "SDS-Q-2026-0003"]
    next_year = await submit(svc, now=FIXED_NOW + timedelta(days=70))
    assert next_year.public_request_id == "SDS-Q-2027-0001"


async def test_concurrent_submissions_get_unique_ids(session_factory, is_postgres):
    svc = service(session_factory)
    users = range(200_000, 200_010)
    if is_postgres:
        results = await asyncio.gather(*(submit(svc, user_id=u) for u in users))
    else:  # SQLite serializes writers; run sequentially there and rely on PostgreSQL for the race
        results = [await submit(svc, user_id=u) for u in users]
    ids = [r.public_request_id for r in results]
    assert len(set(ids)) == 10
    assert sorted(ids) == [f"SDS-Q-2026-{i:04d}" for i in range(1, 11)]


async def test_same_submission_key_is_idempotent(session_factory):
    svc = service(session_factory)
    key = str(uuid.uuid4())
    first = await submit(svc, key=key)
    second = await submit(svc, key=key)
    assert first.created and not second.created
    assert first.public_request_id == second.public_request_id
    async with session_factory() as session:
        assert len((await session.scalars(select(QuoteRequest))).all()) == 1


async def test_submission_key_of_another_user_is_not_revealed(session_factory):
    svc = service(session_factory)
    key = str(uuid.uuid4())
    await submit(svc, key=key)
    with pytest.raises(PermissionError):
        await submit(svc, user_id=999, key=key)


async def test_returning_customer_details_are_updated_not_duplicated(session_factory):
    svc = service(session_factory)
    await submit(svc)
    await submit(svc, email="jane.carter@acme.com", company_name="Acme")
    async with session_factory() as session:
        customers = (await session.scalars(select(Customer))).all()
    assert len(customers) == 1
    assert (customers[0].email, customers[0].company_name) == ("jane.carter@acme.com", "Acme")


async def test_past_pickup_date_rejected_server_side(session_factory):
    with pytest.raises(PickupDateInPast):
        await submit(service(session_factory), pickup_date=date(2026, 10, 1))


async def test_server_side_validation_rejects_bad_data():
    with pytest.raises(ValueError):
        QuoteDraft(**{**DRAFT, "phone": "2155550123"})  # not E.164
    with pytest.raises(ValueError):
        QuoteDraft(**{**DRAFT, "estimated_weight_lb": 0})
    with pytest.raises(ValueError):
        QuoteDraft(**{**DRAFT, "pickup_state": "Texas"})
