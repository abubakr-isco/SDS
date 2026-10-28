from aiogram.methods import SendMessage

from app.keyboards.callbacks import MenuCB, ServiceCB
from tests.conftest import ADMIN_ID, CUSTOMER_ID, make_settings
from tests.harness import alerts, button_texts, last_text, outgoing_texts

MAIN_BUTTONS = ["🚛 Our Services", "📋 Request a Freight Quote", "📍 Track a Shipment", "☎️ Contact SDS", "ℹ️ About SDS"]


async def test_start_shows_welcome_and_main_menu(h):
    requests = await h.send(CUSTOMER_ID, "/start")
    text = last_text(requests)
    assert text.startswith("Welcome to SDS Trucking 🚛")
    assert "Moving America Forward." in text
    assert "What can we help you with today?" in text
    assert button_texts(requests) == MAIN_BUTTONS


async def test_help_lists_commands_and_hides_admin_commands_from_customers(h):
    text = last_text(await h.send(CUSTOMER_ID, "/help"))
    assert "/start" in text and "/help" in text and "/cancel" in text
    assert "/admin" not in text


async def test_help_shows_admin_commands_to_admins(h):
    text = last_text(await h.send(ADMIN_ID, "/help"))
    assert "/admin" in text and "/requests" in text and "/stats" in text


async def test_cancel_without_conversation(h):
    assert "nothing to cancel" in last_text(await h.send(CUSTOMER_ID, "/cancel"))


async def test_menu_navigation_every_screen_has_a_way_back(h):
    for action, expected in [
        ("services", "Our Services"),
        ("contact", "Contact SDS"),
        ("about", "About SDS"),
        ("track", "Track a Shipment"),
    ]:
        requests = await h.click(CUSTOMER_ID, MenuCB(action=action))
        assert expected in last_text(requests)
        assert "🏠 Main Menu" in button_texts(requests)
    requests = await h.click(CUSTOMER_ID, MenuCB(action="home"))
    assert button_texts(requests) == MAIN_BUTTONS


async def test_services_show_only_enabled_services_in_production(h):
    requests = await h.click(CUSTOMER_ID, MenuCB(action="services"))
    text = last_text(requests)
    assert "Full Truckload (FTL)" in text and "Less Than Truckload (LTL)" in text
    assert "Dedicated Transportation" not in text  # not confirmed → hidden
    assert "📋 Request a Quote — Full Truckload (FTL)" in button_texts(requests)


async def test_disabled_service_cannot_be_quoted_with_a_forged_button(h):
    requests = await h.click(CUSTOMER_ID, ServiceCB(key="dedicated"))
    assert alerts(requests) == ["This service isn't available right now. Please contact SDS."]


async def test_services_empty_state_when_nothing_confirmed(h, company):
    for service in company.services:
        service.enabled = False
    text = last_text(await h.click(CUSTOMER_ID, MenuCB(action="services")))
    assert "being updated" in text


async def test_development_mode_shows_unconfirmed_services_and_setup_warnings(ctx, h):
    ctx.settings = make_settings(environment="development")
    services = last_text(await h.click(CUSTOMER_ID, MenuCB(action="services")))
    assert "Dedicated Transportation" in services and "not enabled" in services
    contact = last_text(await h.click(CUSTOMER_ID, MenuCB(action="contact")))
    assert "Setup (development only)" in contact and "website" in contact


async def test_contact_shows_configured_details_and_hides_missing_ones_in_production(h):
    text = last_text(await h.click(CUSTOMER_ID, MenuCB(action="contact")))
    assert "+1 (215) 268-3886" in text
    assert "dispatch@sdsuzinc.com" in text
    assert "Website" not in text and "Office:" not in text  # not configured → not shown
    assert "Setup" not in text


async def test_contact_settings_override_from_database(h, ctx):
    from app.database.repositories import SettingsRepository

    async with ctx.session_factory() as session, session.begin():
        await SettingsRepository(session).set("contact.website", "https://www.sdsuzinc.com")
    requests = await h.click(CUSTOMER_ID, MenuCB(action="contact"))
    assert "https://www.sdsuzinc.com" in last_text(requests)
    assert "🌐 Visit our website" in button_texts(requests)


async def test_unexpected_text_and_media_get_a_helpful_reply(h):
    assert "didn't catch that" in last_text(await h.send(CUSTOMER_ID, "hello?"))
    assert "didn't catch that" in last_text(await h.send_photo_like(CUSTOMER_ID))


async def test_stale_button_is_handled(h):
    requests = await h.click(CUSTOMER_ID, "unknown:payload")
    assert alerts(requests) and "no longer active" in alerts(requests)[0]


async def test_group_chats_are_ignored(h):
    requests = await h.send(-100123, "/start", chat_type="group")
    assert not [r for r in requests if isinstance(r, SendMessage)]


async def test_html_in_user_input_is_escaped(h):
    from app.keyboards.callbacks import QuoteCB

    await h.click(CUSTOMER_ID, MenuCB(action="quote"))
    await h.send(CUSTOMER_ID, "Jane <b>Carter</b>")
    await h.click(CUSTOMER_ID, QuoteCB(action="individual"))
    # The name is echoed later on the review screen; it must be escaped there.
    from tests.conftest import QUOTE_ANSWERS

    requests = []
    for kind, value in QUOTE_ANSWERS[2:]:
        requests = await (h.send(CUSTOMER_ID, value) if kind == "text" else h.click(CUSTOMER_ID, value))
    review = outgoing_texts(requests)[-1]
    assert "Jane &lt;b&gt;Carter&lt;/b&gt;" in review
