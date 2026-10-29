"""Customer- and admin-facing copy. User-provided values are always HTML-escaped."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.database.models import EventType, QuoteStatus, RequestSource
from app.utils.formatting import esc, fmt_date, fmt_datetime, fmt_weight

if TYPE_CHECKING:
    from app.company import CompanyConfig, ContactInfo
    from app.database.models import Customer, QuoteRequest, QuoteRequestEvent
    from app.services.admin import Stats


def welcome(company: CompanyConfig) -> str:
    return (
        f"Welcome to {esc(company.bot_name)} 🚛\n\n"
        f"<b>{esc(company.slogan)}</b>\n\n"
        "We're here to help with your freight transportation needs.\n\n"
        "What can we help you with today?"
    )


MAIN_MENU = "What can we help you with today?"


def help_text(is_admin: bool) -> str:
    lines = [
        "<b>How to use this bot</b>",
        "",
        "/start — main menu",
        "/help — this help message",
        "/cancel — cancel what you're doing and return to the menu",
        "",
        "Use the menu buttons to see our services, request a freight quote, "
        "check a request or shipment, or contact SDS.",
    ]
    if is_admin:
        lines += [
            "",
            "<b>Administrator commands</b>",
            "/admin — dashboard",
            "/requests — recent quote requests",
            "/request SDS-Q-2026-0001 — open a request",
            "/stats — request statistics",
        ]
    return "\n".join(lines)


CANCELLED = "Cancelled. Nothing was submitted."
NOTHING_TO_CANCEL = "There's nothing to cancel."
UNKNOWN_INPUT = "Sorry, I didn't catch that. Please choose an option from the menu."
GENERIC_ERROR = "Something went wrong on our side. Please try again in a moment."
SLOW_DOWN = "You're sending messages quickly. Please wait a moment and try again."
NOT_AUTHORIZED = "This command is only available to SDS administrators."
SESSION_EXPIRED = (
    "Your quote request timed out after a period of inactivity, so nothing was submitted. "
    "You can start a new request any time."
)


def about(company: CompanyConfig) -> str:
    return f"<b>About {esc(company.name)}</b>\n\n{esc(company.about)}\n\n<i>{esc(company.slogan)}</i>"


def services(company: CompanyConfig, *, development: bool) -> str:
    shown = company.services if development else company.enabled_services
    if not shown:
        return (
            "🚛 <b>Our Services</b>\n\n"
            "Our service list is being updated. Please contact SDS to discuss your shipment, "
            "or request a freight quote and our team will follow up."
        )
    parts = ["🚛 <b>Our Services</b>"]
    for service in shown:
        flag = "" if service.enabled else "\n⚠️ <i>Setup: not enabled — hidden from customers in production.</i>"
        parts.append(f"<b>{esc(service.name)}</b>\n{esc(service.description)}{flag}")
    parts.append("Tap a service below to request a quote for it.")
    return "\n\n".join(parts)


def contact(info: ContactInfo, company: CompanyConfig, *, development: bool) -> str:
    rows: list[str] = []
    missing: list[str] = []
    for label, value, key in (
        ("📞 Phone", info.phone, "phone"),
        ("✉️ Email", info.email, "email"),
        ("🌐 Website", str(info.website) if info.website else None, "website"),
        ("🕘 Office hours", info.office_hours, "office_hours"),
        ("📍 Office", info.office_address, "office_address"),
    ):
        if value:
            rows.append(f"{label}: {esc(value)}")
        else:
            missing.append(key)
    text = f"☎️ <b>Contact {esc(company.name)}</b>\n\n"
    text += "\n".join(rows) if rows else "Contact details will be available here soon."
    if development and missing:
        text += "\n\n⚠️ <i>Setup (development only): not configured — " + ", ".join(missing) + ".</i>"
    return text


# ---------------------------------------------------------------- quote wizard

FREIGHT_NOTE = "<i>Choosing a type helps us review your shipment. Our team confirms whether SDS can handle it.</i>"

STEPS = 10


def step(n: int, text: str) -> str:
    return f"📋 <b>Step {n} of {STEPS}</b>\n{text}"


def quote_intro(service_name: str | None) -> str:
    header = "📋 <b>Request a Freight Quote</b>"
    if service_name:
        header += f"\nService: {esc(service_name)}"
    return (
        f"{header}\n\nWe'll ask a few questions about you and your shipment. It takes about 2 minutes. "
        "You can type /cancel at any time.\n\n" + step(1, "What is your <b>full name</b>?")
    )


PROMPTS: dict[str, tuple[int, str]] = {
    "full_name": (1, "What is your <b>full name</b>?"),
    "company": (2, "What is your <b>company name</b>?"),
    "email": (3, "What <b>email address</b> should we use? A business email is preferred."),
    "phone": (
        4,
        "What <b>phone number</b> can we reach you on? Please include the country code, e.g. +1 215 555 0123.\n"
        "You can also tap “Share my phone number” below.",
    ),
    "pickup": (
        5,
        "Where is the <b>pickup</b>? Send the city and state, with the ZIP code if you have it.\nExample: Dallas, TX 75201",
    ),
    "delivery": (
        6,
        "Where is the <b>delivery</b>? Send the city and state, with the ZIP code if you have it.\nExample: Atlanta, GA 30303",
    ),
    "pickup_date": (7, "What is the requested <b>pickup date</b>? Send it as MM/DD/YYYY, or tap a button."),
    "freight_type": (8, "What <b>type of freight</b> is it?\n" + FREIGHT_NOTE),
    "weight": (9, "What is the approximate <b>weight in pounds (lb)</b>? Example: 42000"),
    "details": (
        10,
        "Any <b>shipment details</b> we should know? For example: dimensions, pallet count, "
        "special handling, or delivery windows. (Up to 1,000 characters.)",
    ),
}


def prompt(field: str) -> str:
    n, text = PROMPTS[field]
    return step(n, text)


def quote_review(data: dict) -> str:
    company = data.get("company_name") or "Individual / Not applicable"
    pickup = _place(data, "pickup")
    delivery = _place(data, "delivery")
    lines = [
        "📦 <b>Please review your request</b>",
        "",
        f"<b>Name:</b> {esc(data['full_name'])}",
        f"<b>Company:</b> {esc(company)}",
        f"<b>Email:</b> {esc(data['email'])}",
        f"<b>Phone:</b> {esc(data['phone'])}",
        f"<b>Pickup:</b> {esc(pickup)}",
        f"<b>Delivery:</b> {esc(delivery)}",
        f"<b>Pickup date:</b> {fmt_date(_date(data['pickup_date']))}",
        f"<b>Freight type:</b> {esc(data['freight_type'])}",
        f"<b>Estimated weight:</b> {fmt_weight(data.get('estimated_weight_lb'))}",
        f"<b>Details:</b> {esc(data.get('shipment_details') or 'None provided')}",
    ]
    if data.get("requested_service"):
        lines.insert(2, f"<b>Service:</b> {esc(data['requested_service'])}")
    lines += ["", "If everything looks right, tap <b>Submit Request</b>."]
    return "\n".join(lines)


def quote_confirmation(public_id: str, company: CompanyConfig) -> str:
    return (
        "✅ <b>Your freight quote request has been received.</b>\n\n"
        f"Request ID: <code>{esc(public_id)}</code>\n\n"
        "Our team will review your shipment details and contact you.\n\n"
        f"Thank you for choosing {esc(company.bot_name)}."
    )


SUBMIT_FAILED = (
    "⚠️ We couldn't save your request because of a technical problem, so it has <b>not</b> been submitted.\n\n"
    "Your answers are kept — please tap <b>Submit Request</b> again in a minute. "
    "If the problem continues, contact SDS directly."
)
RATE_LIMITED = (
    "You've submitted several requests in the last hour. To prevent duplicates, please wait a while "
    "before sending another, or contact SDS directly."
)
DATE_NOW_PAST = "The pickup date is now in the past. Please choose a new date."


def _place(data: dict, prefix: str) -> str:
    zip_code = data.get(f"{prefix}_zip")
    return f"{data[f'{prefix}_city']}, {data[f'{prefix}_state']}" + (f" {zip_code}" if zip_code else "")


def _date(value):
    from datetime import date

    return value if isinstance(value, date) else date.fromisoformat(value)


# ---------------------------------------------------------------- tracking

TRACK_PROMPT = (
    "📍 <b>Track a Shipment</b>\n\n"
    "Send your shipment reference or tracking number.\n"
    "You can also send a quote request ID (for example SDS-Q-2026-0001) to check its status."
)
TRACKING_UNAVAILABLE = (
    "Shipment tracking is not currently available through this bot. Please contact SDS for an update."
)
TRACKING_NOT_FOUND = (
    "We couldn't find a shipment with that reference linked to your account. "
    "Please check the reference, or contact SDS for an update."
)
QUOTE_NOT_FOUND = (
    "We couldn't find a quote request with that ID linked to your Telegram account. "
    "Please check the ID, or contact SDS."
)
TRACK_INVALID = "That doesn't look like a valid reference. Please send letters, numbers and dashes only."
TRACK_SLOW_DOWN = "You've made several lookups in a short time. Please wait a few minutes and try again."


def customer_quote_status(request: QuoteRequest, tz: ZoneInfo) -> str:
    return (
        f"📋 <b>Quote request {esc(request.public_request_id)}</b>\n\n"
        f"<b>Status:</b> {request.status.label}\n"
        f"<b>Route:</b> {esc(request.pickup_city)}, {request.pickup_state} → "
        f"{esc(request.delivery_city)}, {request.delivery_state}\n"
        f"<b>Last updated:</b> {fmt_datetime(request.updated_at, tz)}\n\n"
        f"{CUSTOMER_STATUS_NOTES[request.status]}"
    )


def tracking_found(reference: str, status: str, last_updated, tz: ZoneInfo) -> str:
    updated = fmt_datetime(last_updated, tz) if last_updated else "Not available"
    return (
        f"📍 <b>Shipment {esc(reference)}</b>\n\n"
        f"<b>Latest confirmed status:</b> {esc(status)}\n<b>Last updated:</b> {updated}"
    )


# ---------------------------------------------------------------- customer status updates

CUSTOMER_STATUS_NOTES: dict[QuoteStatus, str] = {
    QuoteStatus.NEW: "We've received your request and will review it shortly.",
    QuoteStatus.UNDER_REVIEW: "Our team is reviewing your shipment details.",
    QuoteStatus.AWAITING_CUSTOMER: "We need a little more information. Our team will reach out, or you can contact SDS.",
    QuoteStatus.QUOTED: "A quote has been prepared. Our team will share the details with you directly.",
    QuoteStatus.ACCEPTED: "Thank you — your quote has been accepted. Our team will contact you to coordinate next steps.",
    QuoteStatus.IN_PROGRESS: "Your shipment is in progress. Contact SDS for the latest details.",
    QuoteStatus.COMPLETED: "This request has been completed. Thank you for choosing SDS Trucking.",
    QuoteStatus.CANCELLED: "This request has been cancelled. If that's unexpected, please contact SDS.",
}


def customer_status_update(request: QuoteRequest) -> str:
    return (
        f"🚛 <b>Update on your quote request {esc(request.public_request_id)}</b>\n\n"
        f"<b>Status:</b> {request.status.label}\n\n{CUSTOMER_STATUS_NOTES[request.status]}"
    )


def customer_message(request: QuoteRequest, message: str) -> str:
    return f"🚛 <b>Message from SDS about request {esc(request.public_request_id)}</b>\n\n{esc(message)}"


# ---------------------------------------------------------------- admin


def admin_new_request_text(request: QuoteRequest, customer: Customer, tz: ZoneInfo) -> str:
    company = f" ({esc(customer.company_name)})" if customer.company_name else ""
    service = f"\n<b>Service:</b> {esc(request.requested_service)}" if request.requested_service else ""
    sms = f"\n<b>SMS consent:</b> {sms_consent_label(request, tz)}" if request.source == RequestSource.WEBSITE else ""
    return (
        f"🆕 <b>New quote request {esc(request.public_request_id)}</b>\n"
        f"<b>Source:</b> {source_label(request)}\n\n"
        f"<b>Customer:</b> {esc(customer.full_name)}{company}\n"
        f"<b>Phone:</b> {esc(customer.phone)} · <b>Email:</b> {esc(customer.email)}\n"
        f"<b>Route:</b> {esc(request.pickup_city)}, {request.pickup_state} → "
        f"{esc(request.delivery_city)}, {request.delivery_state}\n"
        f"<b>Pickup:</b> {fmt_date(request.pickup_date)}\n"
        f"<b>Freight:</b> {esc(request.freight_type)} · {fmt_weight(request.estimated_weight_lb)}"
        f"{service}{sms}\n\n"
        f"Open: /request {esc(request.public_request_id)}"
    )


def admin_request_card(request: QuoteRequest, tz: ZoneInfo) -> str:
    c = request.customer
    assigned = esc(request.assigned_admin.display_name) if request.assigned_admin else "Unassigned"
    pickup = f"{esc(request.pickup_city)}, {request.pickup_state}" + (
        f" {request.pickup_zip}" if request.pickup_zip else ""
    )
    delivery = f"{esc(request.delivery_city)}, {request.delivery_state}" + (
        f" {request.delivery_zip}" if request.delivery_zip else ""
    )
    lines = [
        f"📋 <b>{esc(request.public_request_id)}</b> — {request.status.label}",
        f"<b>Source:</b> {source_label(request)}",
        f"<b>Assigned:</b> {assigned}",
        f"<b>Created:</b> {fmt_datetime(request.created_at, tz)}",
        "",
        f"<b>Customer:</b> {esc(c.full_name)}",
        f"<b>Company:</b> {esc(c.company_name or 'Individual / N/A')}",
        f"<b>Email:</b> {esc(c.email)}",
        f"<b>Phone:</b> {esc(c.phone)}",
        "",
        f"<b>Pickup:</b> {pickup}",
        f"<b>Delivery:</b> {delivery}",
        f"<b>Pickup date:</b> {fmt_date(request.pickup_date)}",
        f"<b>Freight:</b> {esc(request.freight_type)}",
        f"<b>Weight:</b> {fmt_weight(request.estimated_weight_lb)}",
    ]
    if request.requested_service:
        lines.append(f"<b>Service:</b> {esc(request.requested_service)}")
    lines.append(f"<b>Details:</b> {esc(request.shipment_details or '—')}")
    if request.source == RequestSource.WEBSITE:
        lines.append(f"<b>SMS consent:</b> {sms_consent_label(request, tz)}")
    if c.telegram_user_id is None:
        lines += ["", WEBSITE_CUSTOMER_NOTE]
    return "\n".join(lines)


WEBSITE_CUSTOMER_NOTE = (
    "<i>Submitted through the website — the customer isn't on Telegram. Contact them by phone or email.</i>"
)


def sms_consent_label(request: QuoteRequest, tz: ZoneInfo) -> str:
    if request.sms_consent_at is None:
        return "No — do not text this customer"
    return f"Yes, for {esc(request.sms_consent_phone)} on {fmt_datetime(request.sms_consent_at, tz)}"


def source_label(request: QuoteRequest) -> str:
    return "🌐 Website form" if request.source == RequestSource.WEBSITE else "💬 Telegram bot"


def admin_request_row(request: QuoteRequest) -> str:
    return f"{request.public_request_id} · {request.status.label} · {request.pickup_state}→{request.delivery_state}"


_EVENT_LABELS = {
    EventType.CREATED: "Request created",
    EventType.STATUS_CHANGED: "Status changed",
    EventType.NOTE_ADDED: "Note",
    EventType.ASSIGNED: "Assigned",
    EventType.CUSTOMER_NOTIFIED: "Customer notified",
    EventType.CUSTOMER_MESSAGED: "Customer messaged",
}


def admin_history(public_id: str, events: Sequence[QuoteRequestEvent], tz: ZoneInfo) -> str:
    lines = [f"🗂 <b>History — {esc(public_id)}</b>", ""]
    for e in events:
        who = esc(e.changed_by.display_name) if e.changed_by else "Customer/system"
        head = f"• {fmt_datetime(e.created_at, tz)} — <b>{_EVENT_LABELS[e.event_type]}</b> ({who})"
        if e.event_type == EventType.STATUS_CHANGED and e.previous_status:
            head += f": {e.previous_status.label} → {e.new_status.label}"
        lines.append(head)
        if e.note:
            lines.append(f"   {esc(e.note)}")
    return "\n".join(lines)


def admin_stats(stats: Stats) -> str:
    lines = ["📊 <b>Quote request statistics</b>", ""]
    for status in QuoteStatus:
        lines.append(f"{status.label}: {stats.by_status.get(status, 0)}")
    lines += [
        "",
        f"<b>Total requests:</b> {stats.total}",
        f"<b>Last 7 days:</b> {stats.last_7_days}",
        f"<b>Last 30 days:</b> {stats.last_30_days}",
        f"<b>Customers:</b> {stats.customers}",
    ]
    return "\n".join(lines)


ADMIN_DASHBOARD = "🛠 <b>SDS Admin</b>\n\nChoose an option."
