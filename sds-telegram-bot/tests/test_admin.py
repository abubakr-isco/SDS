import pytest
from sqlalchemy import select

from app.database.models import EventType, QuoteRequest, QuoteRequestEvent, QuoteStatus
from app.database.repositories import AdminRepository
from app.keyboards.callbacks import AdminCB
from app.services.admin import NotAuthorized
from tests.conftest import ADMIN_2_ID, ADMIN_ID, CUSTOMER_ID, OTHER_CUSTOMER_ID, submit_quote
from tests.harness import alerts, button_texts, last_text, outgoing_texts, sent_to


async def request_id(ctx) -> int:
    async with ctx.session_factory() as session:
        return await session.scalar(select(QuoteRequest.id))


async def events(ctx) -> list[QuoteRequestEvent]:
    async with ctx.session_factory() as session:
        return list((await session.scalars(select(QuoteRequestEvent).order_by(QuoteRequestEvent.id))).all())


# ------------------------------------------------------------------ authorization


@pytest.mark.parametrize("command", ["/admin", "/requests", "/request SDS-Q-2026-0001", "/stats"])
async def test_admin_commands_are_refused_for_customers(h, command):
    assert last_text(await h.send(CUSTOMER_ID, command)) == "This command is only available to SDS administrators."


async def test_forged_admin_callbacks_are_refused(h, ctx):
    await submit_quote(h)
    rid = await request_id(ctx)
    for data in [
        AdminCB(action="view", rid=rid),
        AdminCB(action="apply_status", rid=rid, value="cancelled|1"),
        AdminCB(action="note", rid=rid),
        AdminCB(action="stats"),
    ]:
        requests = await h.click(OTHER_CUSTOMER_ID, data)
        assert alerts(requests) == ["This command is only available to SDS administrators."]
        assert not outgoing_texts(requests)
    async with ctx.session_factory() as session:
        assert (await session.scalar(select(QuoteRequest))).status == QuoteStatus.NEW
    assert [e.event_type for e in await events(ctx)] == [EventType.CREATED]


async def test_deactivated_admin_loses_access_immediately(h, ctx):
    assert "SDS Admin" in last_text(await h.send(ADMIN_ID, "/admin"))
    async with ctx.session_factory() as session, session.begin():
        (await AdminRepository(session).get_by_telegram_id(ADMIN_ID)).is_active = False
    assert "only available to SDS administrators" in last_text(await h.send(ADMIN_ID, "/admin"))
    requests = await h.click(ADMIN_ID, AdminCB(action="stats"))
    assert alerts(requests) == ["This command is only available to SDS administrators."]


async def test_service_layer_rechecks_authorization(ctx):
    with pytest.raises(NotAuthorized):
        await ctx.admin.change_status(CUSTOMER_ID, 1, QuoteStatus.CANCELLED)
    with pytest.raises(NotAuthorized):
        await ctx.admin.recent(CUSTOMER_ID)


async def test_admin_typing_a_note_after_losing_access_is_refused(h, ctx):
    await submit_quote(h)
    rid = await request_id(ctx)
    await h.click(ADMIN_ID, AdminCB(action="note", rid=rid))
    async with ctx.session_factory() as session, session.begin():
        (await AdminRepository(session).get_by_telegram_id(ADMIN_ID)).is_active = False
    assert "only available to SDS administrators" in last_text(await h.send(ADMIN_ID, "sneaky note"))
    assert [e.event_type for e in await events(ctx)] == [EventType.CREATED]


# ------------------------------------------------------------------ dashboard and requests


async def test_dashboard_list_and_details(h, ctx):
    await submit_quote(h)
    requests = await h.send(ADMIN_ID, "/admin")
    assert button_texts(requests) == [
        "🆕 New requests",
        "📥 Recent requests",
        "📊 Statistics",
        "🔁 Retry notifications",
    ]

    requests = await h.click(ADMIN_ID, AdminCB(action="list", value="new"))
    assert "New requests" in last_text(requests)
    assert button_texts(requests)[0] == "SDS-Q-2026-0001 · New · TX→GA"

    card = last_text(await h.send(ADMIN_ID, "/request sds-q-2026-0001"))
    for fragment in ["SDS-Q-2026-0001", "Jane Carter", "Jane@acme-logistics.com", "+12155550123", "Dallas, TX 75201"]:
        assert fragment in card

    assert "was not found" in last_text(await h.send(ADMIN_ID, "/request SDS-Q-2026-9999"))
    assert "Usage" in last_text(await h.send(ADMIN_ID, "/request 1; DROP TABLE customers"))
    assert "Unknown status" in last_text(await h.send(ADMIN_ID, "/requests bogus"))


async def test_status_change_is_saved_with_event_and_customer_is_notified(h, ctx, bot):
    await submit_quote(h)
    rid = await request_id(ctx)

    requests = await h.click(ADMIN_ID, AdminCB(action="status_menu", rid=rid))
    assert "Under Review" in button_texts(requests) and "New" not in button_texts(requests)
    requests = await h.click(ADMIN_ID, AdminCB(action="set_status", rid=rid, value="under_review"))
    assert "✅ Save & notify customer" in button_texts(requests)

    requests = await h.click(ADMIN_ID, AdminCB(action="apply_status", rid=rid, value="under_review|1"))
    assert "New → Under Review" in last_text(requests) and "Customer notified" in last_text(requests)

    customer_msgs = sent_to(requests, CUSTOMER_ID)
    assert len(customer_msgs) == 1
    assert "SDS-Q-2026-0001" in customer_msgs[0].text and "Under Review" in customer_msgs[0].text

    history = await events(ctx)
    change = next(e for e in history if e.event_type == EventType.STATUS_CHANGED)
    assert (change.previous_status, change.new_status) == (QuoteStatus.NEW, QuoteStatus.UNDER_REVIEW)
    assert change.changed_by_admin_id is not None
    assert history[-1].event_type == EventType.CUSTOMER_NOTIFIED


async def test_status_change_without_notifying(h, ctx):
    await submit_quote(h)
    rid = await request_id(ctx)
    requests = await h.click(ADMIN_ID, AdminCB(action="apply_status", rid=rid, value="quoted|0"))
    assert not sent_to(requests, CUSTOMER_ID)
    assert [e.event_type for e in await events(ctx)] == [EventType.CREATED, EventType.STATUS_CHANGED]


async def test_status_change_is_kept_when_customer_cannot_be_reached(h, ctx, bot):
    await submit_quote(h)
    rid = await request_id(ctx)
    bot.mock.blocked_chats.add(CUSTOMER_ID)
    requests = await h.click(ADMIN_ID, AdminCB(action="apply_status", rid=rid, value="cancelled|1"))
    assert "could not be notified (forbidden)" in last_text(requests)
    async with ctx.session_factory() as session:
        assert (await session.scalar(select(QuoteRequest))).status == QuoteStatus.CANCELLED
    assert EventType.CUSTOMER_NOTIFIED not in [e.event_type for e in await events(ctx)]


async def test_same_status_is_rejected(h, ctx):
    await submit_quote(h)
    rid = await request_id(ctx)
    requests = await h.click(ADMIN_ID, AdminCB(action="apply_status", rid=rid, value="new|0"))
    assert alerts(requests) == ["The request already has that status."]


async def test_notes_assignment_history_and_customer_message(h, ctx, settings):
    await ctx.admin.sync_admins([ADMIN_2_ID])
    await submit_quote(h)
    rid = await request_id(ctx)

    await h.click(ADMIN_ID, AdminCB(action="note", rid=rid))
    assert "Note saved" in last_text(await h.send(ADMIN_ID, "Called shipper; dock closes at 4pm."))

    requests = await h.click(ADMIN_ID, AdminCB(action="assign_menu", rid=rid))
    names = button_texts(requests)
    assert any(n.startswith("👤 Me") for n in names) and len(names) == 3  # 2 admins + Back
    async with ctx.session_factory() as session:
        admin2 = await AdminRepository(session).get_by_telegram_id(ADMIN_2_ID)
    requests = await h.click(ADMIN_ID, AdminCB(action="assign", rid=rid, value=str(admin2.id)))
    assert f"Assigned to {admin2.display_name}" in last_text(requests)

    await h.click(ADMIN_ID, AdminCB(action="message", rid=rid))
    requests = await h.send(ADMIN_ID, "Could you confirm the pallet dimensions?")
    assert "delivered" in last_text(requests)
    assert "pallet dimensions" in sent_to(requests, CUSTOMER_ID)[0].text

    history = last_text(await h.click(ADMIN_ID, AdminCB(action="history", rid=rid)))
    for fragment in ["Request created", "Note", "dock closes at 4pm", "Assigned", "Customer messaged"]:
        assert fragment in history

    async with ctx.session_factory() as session:
        request = await session.scalar(select(QuoteRequest))
    assert request.assigned_admin_id == admin2.id


async def test_customer_never_sees_internal_notes(h, ctx, bot):
    await submit_quote(h)
    rid = await request_id(ctx)
    await h.click(ADMIN_ID, AdminCB(action="note", rid=rid))
    await h.send(ADMIN_ID, "INTERNAL: price sensitive customer")
    assert not any("INTERNAL" in m.text for m in sent_to(bot.mock.requests, CUSTOMER_ID))


async def test_stats(h, ctx):
    await submit_quote(h)
    rid = await request_id(ctx)
    await h.click(ADMIN_ID, AdminCB(action="apply_status", rid=rid, value="quoted|0"))
    text = last_text(await h.send(ADMIN_ID, "/stats"))
    assert "Quoted: 1" in text and "New: 0" in text
    assert "Total requests:</b> 1" in text and "Customers:</b> 1" in text
