import uuid

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.database.models import AdminNotification, Customer, QuoteRequest, RequestSource
from app.database.repositories import QuoteRepository
from app.keyboards.callbacks import AdminCB
from app.web import create_web_app
from tests.conftest import ADMIN_ID, CUSTOMER_ID, make_settings
from tests.harness import alerts, button_texts, last_text, sent_to

SITE = "https://www.sdsuzinc.com"

VALID = {
    "fullName": "Maria Lopez",
    "companyName": "Lopez Produce LLC",
    "email": "maria@lopezproduce.com",
    "phone": "(215) 555-0144",
    "pickupLocation": "Philadelphia, PA 19103",
    "deliveryLocation": "Columbus, OH",
    "pickupDate": "2026-11-04",
    "freightType": "Temperature-Controlled Freight",
    "estimatedWeight": "38,000",
    "details": "18 pallets, keep at 34°F",
    "website": "",
}


@pytest_asyncio.fixture
async def client(ctx, bot):
    ctx.settings = make_settings(website_allowed_origins=SITE, website_quotes_per_hour_per_ip=3)
    async with TestClient(TestServer(create_web_app(ctx, bot))) as test_client:
        yield test_client
    await ctx.drain()


async def post(client, payload=None, origin=SITE, **kwargs):
    headers = {"Origin": origin} if origin else {}
    body = {**VALID, "submissionKey": str(uuid.uuid4()), **(payload or {})}
    return await client.post("/api/quote", json=body, headers=headers, **kwargs)


async def rows(ctx, model) -> int:
    async with ctx.session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_website_request_is_saved_and_sent_to_admins_in_telegram(client, ctx, bot):
    response = await post(client)
    assert response.status == 201
    assert await response.json() == {"ok": True, "requestId": "SDS-Q-2026-0001"}
    assert response.headers["Access-Control-Allow-Origin"] == SITE

    async with ctx.session_factory() as session:
        request = await QuoteRepository(session).get_by_public_id("SDS-Q-2026-0001")
        assert request.source == RequestSource.WEBSITE
        assert request.customer.telegram_user_id is None
        assert (request.pickup_city, request.pickup_state, request.pickup_zip) == ("Philadelphia", "PA", "19103")
        assert request.estimated_weight_lb == 38000
        assert request.freight_type == "Temperature-Controlled Freight"
        assert request.customer.phone == "+12155550144"

    await ctx.drain()
    [notification] = sent_to(bot.mock.requests, ADMIN_ID)
    for fragment in [
        "SDS-Q-2026-0001",
        "Website form",
        "Maria Lopez",
        "+12155550144",
        "Philadelphia, PA → Columbus, OH",
    ]:
        assert fragment in notification.text


async def test_resubmitting_the_same_form_does_not_duplicate(client, ctx):
    key = str(uuid.uuid4())
    first = await post(client, {"submissionKey": key})
    second = await post(client, {"submissionKey": key})
    assert (first.status, second.status) == (201, 200)
    assert (await first.json())["requestId"] == (await second.json())["requestId"]
    assert await rows(ctx, QuoteRequest) == 1
    assert await rows(ctx, AdminNotification) == 1


async def test_same_email_reuses_the_website_customer(client, ctx):
    await post(client)
    await post(client, {"phone": "+1 215 555 0199"})
    assert await rows(ctx, Customer) == 1
    assert await rows(ctx, QuoteRequest) == 2


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"fullName": ""}, "fullName"),
        ({"email": "maria-at-lopez"}, "email"),
        ({"phone": "12345"}, "phone"),
        ({"pickupLocation": "Philadelphia"}, "pickupLocation"),
        ({"deliveryLocation": "Toronto, ON"}, "deliveryLocation"),
        ({"pickupDate": "2026-10-01"}, "pickupDate"),
        ({"freightType": "Hazmat"}, "freightType"),
        ({"estimatedWeight": "-5"}, "estimatedWeight"),
        ({"details": "x" * 1001}, "details"),
        ({"fullName": 123}, "fullName"),
    ],
)
async def test_invalid_fields_return_field_errors(client, ctx, changes, field):
    response = await post(client, changes)
    assert response.status == 422
    body = await response.json()
    assert body["ok"] is False and field in body["errors"]
    assert await rows(ctx, QuoteRequest) == 0


async def test_optional_fields_can_be_empty(client, ctx):
    response = await post(client, {"companyName": "", "estimatedWeight": "", "details": ""})
    assert response.status == 201
    async with ctx.session_factory() as session:
        request = await session.scalar(select(QuoteRequest))
    assert request.estimated_weight_lb is None and request.shipment_details is None


async def test_sms_consent_is_recorded_with_time_and_number(client, ctx, bot):
    response = await post(client, {"smsConsent": True})
    assert response.status == 201
    async with ctx.session_factory() as session:
        request = await session.scalar(select(QuoteRequest))
    assert request.sms_consent_at is not None
    assert request.sms_consent_phone == "+12155550144"

    await ctx.drain()
    [notification] = sent_to(bot.mock.requests, ADMIN_ID)
    assert "SMS consent:</b> Yes, for +12155550144" in notification.text


@pytest.mark.parametrize("value", [None, False, "true", 1])
async def test_anything_but_true_is_no_sms_consent(client, ctx, bot, value):
    payload = {} if value is None else {"smsConsent": value}
    assert (await post(client, payload)).status == 201
    async with ctx.session_factory() as session:
        request = await session.scalar(select(QuoteRequest))
    assert request.sms_consent_at is None and request.sms_consent_phone is None

    await ctx.drain()
    [notification] = sent_to(bot.mock.requests, ADMIN_ID)
    assert "SMS consent:</b> No" in notification.text


async def test_honeypot_submissions_are_dropped(client, ctx):
    response = await post(client, {"website": "http://spam.example"})
    assert response.status == 400
    assert await rows(ctx, QuoteRequest) == 0


async def test_per_ip_rate_limit(client, ctx):
    for _ in range(3):
        assert (await post(client)).status == 201
    response = await post(client)
    assert response.status == 429
    assert await rows(ctx, QuoteRequest) == 3


async def test_cors(client):
    ok = await client.options("/api/quote", headers={"Origin": SITE, "Access-Control-Request-Method": "POST"})
    assert ok.status == 204 and ok.headers["Access-Control-Allow-Origin"] == SITE
    assert "POST" in ok.headers["Access-Control-Allow-Methods"]

    bad = await client.options("/api/quote", headers={"Origin": "https://evil.example"})
    assert bad.status == 403
    assert (await post(client, origin="https://evil.example")).status == 403
    assert (await post(client, origin=None)).status == 201  # non-browser clients still pass validation + limits


async def test_database_failure_returns_503_and_saves_nothing(client, ctx, monkeypatch):
    async def broken(self, year):
        raise OperationalError("INSERT ...", {}, ConnectionError("db down"))

    monkeypatch.setattr(QuoteRepository, "next_public_id", broken)
    response = await post(client)
    assert response.status == 503
    body = await response.json()
    assert body == {"ok": False, "error": "unavailable"}
    assert await rows(ctx, Customer) == 0


async def test_malformed_requests(client):
    assert (await client.post("/api/quote", data="hello", headers={"Origin": SITE})).status == 415
    assert (
        await client.post("/api/quote", data="{not json", headers={"Origin": SITE, "Content-Type": "application/json"})
    ).status == 400
    assert (await client.post("/api/quote", json=["a"], headers={"Origin": SITE})).status == 400
    huge = await client.post("/api/quote", json={**VALID, "details": "x" * 20_000}, headers={"Origin": SITE})
    assert huge.status == 413


async def test_healthz(client):
    response = await client.get("/healthz")
    assert response.status == 200 and await response.json() == {"ok": True}


# ------------------------------------------------------------------ admin handling of website requests


async def test_admin_sees_website_source_and_no_telegram_only_actions(client, ctx, h):
    await post(client)
    async with ctx.session_factory() as session:
        rid = await session.scalar(select(QuoteRequest.id))

    requests = await h.send(ADMIN_ID, "/request SDS-Q-2026-0001")
    card = last_text(requests)
    assert "Website form" in card and "isn't on Telegram" in card and "maria@lopezproduce.com" in card
    assert "✉️ Message customer" not in button_texts(requests)

    requests = await h.click(ADMIN_ID, AdminCB(action="set_status", rid=rid, value="under_review"))
    assert button_texts(requests)[0] == "💾 Save"

    requests = await h.click(ADMIN_ID, AdminCB(action="apply_status", rid=rid, value="under_review|1"))
    assert "Website customer — not notified" in last_text(requests)

    requests = await h.click(ADMIN_ID, AdminCB(action="message", rid=rid))
    assert alerts(requests) and "website form" in alerts(requests)[0]


async def test_website_requests_are_not_visible_to_telegram_users(client, h):
    await post(client)
    from app.keyboards.callbacks import MenuCB

    await h.click(CUSTOMER_ID, MenuCB(action="track"))
    assert "couldn't find a quote request" in last_text(await h.send(CUSTOMER_ID, "SDS-Q-2026-0001"))


async def test_myid_command(h):
    assert last_text(await h.send(CUSTOMER_ID, "/myid")) == f"Your Telegram user ID: <code>{CUSTOMER_ID}</code>"
