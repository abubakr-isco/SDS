import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.database.models import AdminNotification, NotificationStatus, QuoteRequest
from app.database.repositories import NotificationRepository
from app.keyboards.callbacks import AdminCB
from tests.conftest import ADMIN_2_ID, ADMIN_ID, submit_quote
from tests.harness import last_text, sent_to


async def notifications(ctx) -> list[AdminNotification]:
    async with ctx.session_factory() as session:
        return list((await session.scalars(select(AdminNotification).order_by(AdminNotification.id))).all())


async def test_admin_notification_failure_keeps_the_request_and_customer_confirmation(h, ctx, bot):
    bot.mock.blocked_chats.add(ADMIN_ID)
    requests = await submit_quote(h)
    assert "SDS-Q-2026-0001" in last_text(requests)  # customer still gets a truthful confirmation
    await ctx.drain()

    async with ctx.session_factory() as session:
        assert await session.scalar(select(QuoteRequest.public_request_id)) == "SDS-Q-2026-0001"
    [n] = await notifications(ctx)
    assert (n.status, n.attempts, n.last_error) == (NotificationStatus.FAILED, 1, "forbidden")


async def test_retry_delivers_once_and_does_not_duplicate(h, ctx, bot, clock):
    bot.mock.blocked_chats.add(ADMIN_ID)
    await submit_quote(h)
    await ctx.drain()
    bot.mock.blocked_chats.clear()
    before = len(bot.mock.requests)

    report = await ctx.notifications.dispatch(bot, now=clock())
    assert (report.sent, report.failed) == (1, 0)
    report = await ctx.notifications.dispatch(bot, now=clock())  # nothing left to send
    assert (report.sent, report.failed) == (0, 0)

    delivered = [m for m in sent_to(bot.mock.requests[before:], ADMIN_ID) if "New quote request" in m.text]
    assert len(delivered) == 1
    [n] = await notifications(ctx)
    assert n.status == NotificationStatus.SENT and n.attempts == 2 and n.sent_at is not None
    async with ctx.session_factory() as session:
        assert len((await session.scalars(select(QuoteRequest))).all()) == 1


async def test_concurrent_dispatchers_send_each_notification_once(h, ctx, bot, clock):
    await ctx.admin.sync_admins([ADMIN_2_ID])
    bot.mock.blocked_chats.update({ADMIN_ID, ADMIN_2_ID})
    await submit_quote(h)
    await ctx.drain()
    bot.mock.blocked_chats.clear()
    before = len(bot.mock.requests)

    await asyncio.gather(*(ctx.notifications.dispatch(bot, now=clock()) for _ in range(4)))
    new = bot.mock.requests[before:]
    assert len(sent_to(new, ADMIN_ID)) == 1 and len(sent_to(new, ADMIN_2_ID)) == 1


async def test_stuck_sending_rows_are_recovered_but_fresh_ones_are_not_touched(h, ctx, bot, clock):
    bot.mock.blocked_chats.add(ADMIN_ID)
    await submit_quote(h)
    await ctx.drain()
    [n] = await notifications(ctx)
    async with ctx.session_factory() as session, session.begin():
        assert await NotificationRepository(session).claim(
            n.id, now=clock(), stale_before=clock() - timedelta(minutes=5)
        )
    bot.mock.blocked_chats.clear()

    assert (await ctx.notifications.dispatch(bot, now=clock())).sent == 0  # just claimed: not stale yet
    later = clock() + timedelta(minutes=10)
    assert (await ctx.notifications.dispatch(bot, now=later)).sent == 1


async def test_retries_stop_after_max_attempts(h, ctx, bot, clock):
    bot.mock.blocked_chats.add(ADMIN_ID)
    await submit_quote(h)
    await ctx.drain()
    for _ in range(ctx.settings.notification_max_attempts + 3):
        await ctx.notifications.dispatch(bot, now=clock())
    [n] = await notifications(ctx)
    assert n.attempts == ctx.settings.notification_max_attempts


async def test_admin_can_retry_from_the_dashboard(h, ctx, bot):
    bot.mock.blocked_chats.add(ADMIN_ID)
    await submit_quote(h)
    await ctx.drain()
    bot.mock.blocked_chats.clear()
    requests = await h.click(ADMIN_ID, AdminCB(action="retry"))
    assert "Sent: 1" in last_text(requests)


async def test_admin_added_after_submission_is_not_spammed_with_old_requests(h, ctx, bot, clock):
    await submit_quote(h)
    await ctx.drain()
    await ctx.admin.sync_admins([ADMIN_2_ID])
    await ctx.notifications.dispatch(bot, now=clock())
    assert not sent_to(bot.mock.requests, ADMIN_2_ID)
