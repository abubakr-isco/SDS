from datetime import UTC, datetime

from app.keyboards.callbacks import MenuCB
from app.services.tracking import TrackingOutcome, TrackingResult
from tests.conftest import CUSTOMER_ID, OTHER_CUSTOMER_ID, submit_quote
from tests.harness import last_text


async def lookup(h, user_id, reference):
    await h.click(user_id, MenuCB(action="track"))
    return last_text(await h.send(user_id, reference))


async def test_tracking_not_configured_is_honest(h):
    text = await lookup(h, CUSTOMER_ID, "PRO-123456")
    assert text == "Shipment tracking is not currently available through this bot. Please contact SDS for an update."


async def test_customer_can_check_their_own_quote_request(h):
    await submit_quote(h)
    text = await lookup(h, CUSTOMER_ID, "sds-q-2026-0001")
    assert "SDS-Q-2026-0001" in text and "Status:</b> New" in text and "Dallas, TX → Atlanta, GA" in text


async def test_other_customers_cannot_see_a_quote_request(h):
    await submit_quote(h)
    text = await lookup(h, OTHER_CUSTOMER_ID, "SDS-Q-2026-0001")
    assert "couldn't find a quote request" in text
    assert "Dallas" not in text and "Jane" not in text


async def test_invalid_reference(h):
    assert "valid reference" in await lookup(h, CUSTOMER_ID, "'; DROP TABLE shipments; --")


async def test_lookups_are_rate_limited(h):
    for _ in range(5):
        await lookup(h, CUSTOMER_ID, "PRO-1")
    assert "several lookups" in await lookup(h, CUSTOMER_ID, "PRO-1")


class FakeTrackingProvider:
    """Stands in for a future TMS integration and follows the provider contract."""

    is_configured = True

    def __init__(self):
        self.shipments = {"PRO-777": (CUSTOMER_ID, "Delivered", datetime(2026, 10, 27, 21, 5, tzinfo=UTC))}

    async def lookup(self, reference, telegram_user_id):
        record = self.shipments.get(reference)
        if record is None or record[0] != telegram_user_id:
            return TrackingResult(TrackingOutcome.NOT_FOUND, reference)
        return TrackingResult(TrackingOutcome.FOUND, reference, status=record[1], last_updated=record[2])


async def test_integrated_provider_shows_only_authorized_shipments(h, ctx):
    ctx.tracking = FakeTrackingProvider()
    text = await lookup(h, CUSTOMER_ID, "pro-777")
    assert "PRO-777" in text and "Latest confirmed status:</b> Delivered" in text
    assert "Oct 27, 2026 4:05 PM CDT" in text  # shown in the company timezone

    other = await lookup(h, OTHER_CUSTOMER_ID, "PRO-777")
    assert "couldn't find a shipment" in other and "Delivered" not in other
