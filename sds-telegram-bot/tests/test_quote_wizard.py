import asyncio
from datetime import date

from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import ReplyKeyboardRemove
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.database.models import AdminNotification, Customer, QuoteRequest, QuoteRequestEvent, QuoteStatus
from app.database.repositories import QuoteRepository
from app.keyboards.callbacks import MenuCB, QuoteCB, ServiceCB
from tests.conftest import ADMIN_ID, CUSTOMER_ID, QUOTE_ANSWERS, fill_quote, submit_quote
from tests.harness import alerts, button_texts, last_text, outgoing_texts, sent_to


async def count(ctx, model) -> int:
    async with ctx.session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_wizard_progresses_through_every_step_to_review(h):
    requests = await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    assert "Step 1 of 10" in last_text(requests) and "full name" in last_text(requests)

    expected_prompts = [
        "Step 2 of 10",
        "Step 3 of 10",
        "Step 4 of 10",
        "Step 5 of 10",
        "Step 6 of 10",
        "Step 7 of 10",
        "Step 8 of 10",
        "Step 9 of 10",
        "Step 10 of 10",
        "Please review your request",
    ]
    for (kind, value), prompt in zip(QUOTE_ANSWERS, expected_prompts, strict=True):
        requests = await (h.send(CUSTOMER_ID, value) if kind == "text" else h.click(CUSTOMER_ID, value))
        assert prompt in last_text(requests), (value, outgoing_texts(requests))

    review = last_text(requests)
    for fragment in [
        "Jane Carter",
        "Acme Logistics",
        "Jane@acme-logistics.com",
        "+12155550123",
        "Dallas, TX 75201",
        "Atlanta, GA",
        "Wed, Nov 4, 2026",
        "General Freight",
        "42,000 lb",
        "22 pallets",
    ]:
        assert fragment in review
    assert button_texts(requests) == ["✅ Submit Request", "✏️ Edit Information", "❌ Cancel"]


async def test_phone_step_offers_contact_sharing_and_removes_the_keyboard_afterwards(h):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    for _, value in QUOTE_ANSWERS[:2]:
        await h.send(CUSTOMER_ID, value)
    requests = await h.send(CUSTOMER_ID, "jane@acme.com")
    assert "📱 Share my phone number" in button_texts(requests)

    requests = await h.send_contact(CUSTOMER_ID, "12155550123")
    removed = [r for r in requests if isinstance(r, SendMessage) and isinstance(r.reply_markup, ReplyKeyboardRemove)]
    assert removed and "Phone number saved" in removed[0].text
    assert "Step 5 of 10" in last_text(requests)


async def test_someone_elses_contact_card_is_rejected(h):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    for _, value in QUOTE_ANSWERS[:3]:
        await h.send(CUSTOMER_ID, value)
    requests = await h.send_contact(CUSTOMER_ID, "12155550199", contact_user_id=555)
    assert "share your own phone number" in last_text(requests)


async def test_invalid_answers_keep_the_customer_on_the_same_step(h):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    await h.send(CUSTOMER_ID, "Jane Carter")
    await h.send(CUSTOMER_ID, "Acme")

    assert "valid email" in last_text(await h.send(CUSTOMER_ID, "jane-at-acme"))
    assert "Step 4 of 10" in last_text(await h.send(CUSTOMER_ID, "jane@acme.com"))

    assert "country code" in last_text(await h.send(CUSTOMER_ID, "12345"))
    assert "Step 5 of 10" in last_text(await h.send(CUSTOMER_ID, "+44 20 7946 0958"))  # non-US accepted

    assert "Example: Dallas, TX 75201" in last_text(await h.send(CUSTOMER_ID, "Dallas"))
    await h.send(CUSTOMER_ID, "Dallas, TX")
    await h.send(CUSTOMER_ID, "Atlanta, GA")

    assert "in the past" in last_text(await h.send(CUSTOMER_ID, "10/01/2026"))
    assert "MM/DD/YYYY" in last_text(await h.send(CUSTOMER_ID, "soon"))
    assert "Step 8 of 10" in last_text(await h.click(CUSTOMER_ID, QuoteCB(action="tomorrow")))

    assert "choose one of the options" in last_text(await h.send(CUSTOMER_ID, "steel coils"))
    await h.click(CUSTOMER_ID, QuoteCB(action="freight", value="machinery"))

    assert "greater than zero" in last_text(await h.send(CUSTOMER_ID, "0"))
    assert "greater than zero" in last_text(await h.send(CUSTOMER_ID, "-200"))
    assert "Step 10 of 10" in last_text(await h.click(CUSTOMER_ID, QuoteCB(action="weight_unknown")))

    assert "1000 characters" in last_text(await h.send(CUSTOMER_ID, "x" * 1001))
    review = last_text(await h.click(CUSTOMER_ID, QuoteCB(action="skip_details")))
    assert "Thu, Oct 29, 2026" in review and "Not sure" in review and "None provided" in review


async def test_non_text_messages_during_the_wizard(h):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    assert "reply with a text message" in last_text(await h.send_photo_like(CUSTOMER_ID))


async def test_individual_company_option(h):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    await h.send(CUSTOMER_ID, "Jane Carter")
    assert "Step 3 of 10" in last_text(await h.click(CUSTOMER_ID, QuoteCB(action="individual")))


async def test_back_button_returns_to_previous_step(h):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    await h.send(CUSTOMER_ID, "Jane Carter")
    await h.send(CUSTOMER_ID, "Acme")
    assert "Step 2 of 10" in last_text(await h.click(CUSTOMER_ID, QuoteCB(action="back")))


async def test_edit_a_single_field_from_review(h):
    await fill_quote(h)
    await h.click(CUSTOMER_ID, QuoteCB(action="edit"))
    assert "Step 9 of 10" in last_text(await h.click(CUSTOMER_ID, QuoteCB(action="edit_field", value="weight")))
    review = last_text(await h.send(CUSTOMER_ID, "18000"))
    assert "Please review your request" in review and "18,000 lb" in review and "Jane Carter" in review


async def test_cancel_by_command_button_and_reply_keyboard(h, ctx):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    await h.send(CUSTOMER_ID, "Jane Carter")
    assert "Cancelled. Nothing was submitted." in last_text(await h.send(CUSTOMER_ID, "/cancel"))

    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    assert "Cancelled" in last_text(await h.click(CUSTOMER_ID, QuoteCB(action="cancel")))

    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    for _, value in QUOTE_ANSWERS[:3]:
        await h.send(CUSTOMER_ID, value)
    requests = await h.send(CUSTOMER_ID, "❌ Cancel")  # reply-keyboard button on the phone step
    assert any(isinstance(r.reply_markup, ReplyKeyboardRemove) for r in requests if isinstance(r, SendMessage))
    assert await count(ctx, QuoteRequest) == 0
    # After cancelling, text is no longer treated as wizard input.
    assert "didn't catch that" in last_text(await h.send(CUSTOMER_ID, "jane@acme.com"))


async def test_quote_submission_saves_everything_and_confirms_with_request_id(h, ctx, bot):
    requests = await submit_quote(h)
    confirmation = last_text(requests)
    assert "Your freight quote request has been received." in confirmation
    assert "SDS-Q-2026-0001" in confirmation
    assert "Thank you for choosing SDS Trucking." in confirmation

    async with ctx.session_factory() as session:
        request = await QuoteRepository(session).get_by_public_id("SDS-Q-2026-0001")
        assert request.status == QuoteStatus.NEW
        assert (request.pickup_city, request.pickup_state, request.pickup_zip) == ("Dallas", "TX", "75201")
        assert (request.delivery_city, request.delivery_state, request.delivery_zip) == ("Atlanta", "GA", None)
        assert request.pickup_date == date(2026, 11, 4)
        assert request.estimated_weight_lb == 42000
        assert request.customer.email == "Jane@acme-logistics.com"
        assert request.customer.phone == "+12155550123"
        events = (await session.scalars(select(QuoteRequestEvent))).all()
        assert [e.event_type.value for e in events] == ["created"]

    await ctx.drain()
    admin_messages = sent_to(bot.mock.requests, ADMIN_ID)
    assert len(admin_messages) == 1 and "SDS-Q-2026-0001" in admin_messages[0].text
    # After submitting, the conversation is over.
    assert "didn't catch that" in last_text(await h.send(CUSTOMER_ID, "hello"))


async def test_quote_started_from_a_service_records_the_service(h, ctx):
    await h.click(CUSTOMER_ID, ServiceCB(key="ftl"))
    for kind, value in QUOTE_ANSWERS:
        await (h.send(CUSTOMER_ID, value) if kind == "text" else h.click(CUSTOMER_ID, value))
    await h.click(CUSTOMER_ID, QuoteCB(action="submit"))
    async with ctx.session_factory() as session:
        request = await session.scalar(select(QuoteRequest))
    assert request.requested_service == "Full Truckload (FTL)"


async def test_double_tap_on_submit_creates_exactly_one_request(h, ctx):
    await fill_quote(h)
    first, second = await asyncio.gather(
        h.click(CUSTOMER_ID, QuoteCB(action="submit")), h.click(CUSTOMER_ID, QuoteCB(action="submit"))
    )
    assert await count(ctx, QuoteRequest) == 1
    assert await count(ctx, AdminNotification) == 1
    confirmations = [t for t in outgoing_texts(first + second) if "has been received" in t]
    assert confirmations and all("SDS-Q-2026-0001" in t for t in confirmations)


async def test_submit_button_after_completion_does_not_resubmit(h, ctx):
    await submit_quote(h)
    requests = await h.click(CUSTOMER_ID, QuoteCB(action="submit"))
    assert alerts(requests) and "no longer active" in alerts(requests)[0]
    assert await count(ctx, QuoteRequest) == 1


async def test_database_failure_never_shows_success_and_allows_retry(h, ctx, bot, monkeypatch):
    original = QuoteRepository.next_public_id

    async def broken(self, year):
        raise OperationalError("INSERT ...", {}, ConnectionError("db down"))

    monkeypatch.setattr(QuoteRepository, "next_public_id", broken)
    requests = await submit_quote(h)
    texts = outgoing_texts(requests)
    assert not any("has been received" in t for t in texts)
    assert "<b>not</b> been submitted" in texts[-1]
    assert "db down" not in "".join(texts)  # internal details never reach the user
    assert button_texts(requests)[0] == "✅ Submit Request"  # answers kept, can retry
    assert await count(ctx, QuoteRequest) == 0
    assert await count(ctx, Customer) == 0  # the transaction rolled back completely

    monkeypatch.setattr(QuoteRepository, "next_public_id", original)
    requests = await h.click(CUSTOMER_ID, QuoteCB(action="submit"))
    assert "SDS-Q-2026-0001" in last_text(requests)
    assert await count(ctx, QuoteRequest) == 1


async def test_submission_rate_limit(h, ctx):
    ctx.flood_limiter.max_events = 10_000  # this test clicks faster than any person; isolate the hourly limit
    for i in range(3):
        assert "SDS-Q-2026-000" in last_text(await submit_quote(h)), i
    requests = await submit_quote(h)
    assert "several requests in the last hour" in last_text(requests)
    assert await count(ctx, QuoteRequest) == 3


async def test_abandoned_conversation_expires(h, clock, ctx):
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    await h.send(CUSTOMER_ID, "Jane Carter")
    clock.advance(minutes=61)
    requests = await h.send(CUSTOMER_ID, "Acme Logistics")
    assert "timed out" in outgoing_texts(requests)[0]
    assert await count(ctx, QuoteRequest) == 0
    assert "didn't catch that" in last_text(await h.send(CUSTOMER_ID, "Acme Logistics"))


async def test_pickup_date_rolled_into_the_past_while_reviewing(h, clock, ctx):
    clock.advance(hours=13, minutes=30)  # 11:30 PM CT on Oct 28
    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    for kind, value in QUOTE_ANSWERS[:6]:
        await h.send(CUSTOMER_ID, value)
    await h.click(CUSTOMER_ID, QuoteCB(action="today"))
    for kind, value in QUOTE_ANSWERS[7:]:
        await (h.send(CUSTOMER_ID, value) if kind == "text" else h.click(CUSTOMER_ID, value))
    clock.advance(minutes=40)  # now 12:10 AM CT on Oct 29 — "today" (Oct 28) is in the past
    requests = await h.click(CUSTOMER_ID, QuoteCB(action="submit"))
    assert "now in the past" in last_text(requests) and "Step 7 of 10" in last_text(requests)
    assert await count(ctx, QuoteRequest) == 0
    review = last_text(await h.click(CUSTOMER_ID, QuoteCB(action="today")))
    assert "Thu, Oct 29, 2026" in review
    assert "SDS-Q-2026-0001" in last_text(await h.click(CUSTOMER_ID, QuoteCB(action="submit")))


async def test_review_message_buttons_are_removed_while_saving(h):
    await fill_quote(h)
    requests = await h.click(CUSTOMER_ID, QuoteCB(action="submit"))
    edits = [r for r in requests if isinstance(r, EditMessageText)]
    assert "Submitting" in edits[0].text and edits[0].reply_markup is None


def _dead_database():
    from app.database.session import create_engine, create_session_factory

    return create_session_factory(create_engine("sqlite+aiosqlite:////nonexistent-dir/sds.db"))


async def test_real_database_outage_during_submission(h, ctx):
    await fill_quote(h)
    ctx.quotes._sessions = _dead_database()
    requests = await h.click(CUSTOMER_ID, QuoteCB(action="submit"))
    assert "<b>not</b> been submitted" in last_text(requests)
    assert not any("has been received" in t for t in outgoing_texts(requests))


async def test_database_outage_gives_a_friendly_message_and_contact_still_works(h, ctx):
    ctx.admin._sessions = _dead_database()
    ctx.session_factory = _dead_database()
    text = last_text(await h.send(ADMIN_ID, "/admin"))
    assert text.startswith("Our system is temporarily unavailable")
    assert "sqlite" not in text.lower() and "error" not in text.lower()
    contact = last_text(await h.click(CUSTOMER_ID, MenuCB(action="contact")))
    assert "+1 (215) 268-3886" in contact  # contact details don't depend on the database
