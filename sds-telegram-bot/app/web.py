"""HTTP endpoint for the website quote form.

POST /api/quote  — JSON body from the website form → saved as a quote request (source=website)
                   → administrators are notified in Telegram, exactly like bot submissions.
GET  /healthz    — liveness check for monitoring.

The website never sees the bot token. Browser access is limited to WEBSITE_ALLOWED_ORIGINS.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiohttp import web
from pydantic import ValidationError as PydanticValidationError

from app.context import AppContext
from app.database.models import RequestSource
from app.services.quotes import PickupDateInPast, QuoteDraft
from app.utils.ratelimit import SlidingWindowLimiter
from app.utils.validation import (
    ValidationError,
    parse_company,
    parse_details,
    parse_email,
    parse_full_name,
    parse_location,
    parse_phone,
    parse_pickup_date,
    parse_weight,
)

log = logging.getLogger(__name__)

MAX_BODY_BYTES = 16 * 1024
CTX = web.AppKey("ctx", AppContext)
BOT = web.AppKey("bot", Bot)
SAVE_LIMITER = web.AppKey("save_limiter", SlidingWindowLimiter)
FLOOD_LIMITER = web.AppKey("flood_limiter", SlidingWindowLimiter)

CORS_HEADERS = {
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept",
    "Access-Control-Max-Age": "600",
}


def _origin_allowed(ctx: AppContext, origin: str | None) -> bool:
    if origin is None:
        return True  # not a browser cross-origin request (e.g. curl, server-to-server); still rate limited
    allowed = ctx.settings.website_allowed_origins
    if not allowed:
        return ctx.settings.is_development  # convenience for local work only
    return origin.rstrip("/") in allowed


def _json(data: dict[str, Any], status: int, origin: str | None) -> web.Response:
    response = web.json_response(data, status=status)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response


def _client_ip(request: web.Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote or "unknown"


def _field(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("Invalid value.")
    return value.strip()


def validate_website_payload(payload: dict[str, Any], ctx: AppContext) -> tuple[dict[str, str], QuoteDraft | None]:
    """Server-side validation of the website form. Keys of the error dict are the form's field names."""
    errors: dict[str, str] = {}
    values: dict[str, Any] = {}

    def check(name: str, parse: Callable[[str], dict[str, Any]], *, required: bool, missing: str) -> None:
        try:
            raw = _field(payload, name)
            if not raw:
                if required:
                    errors[name] = missing
                return
            values.update(parse(raw))
        except ValidationError as exc:
            errors[name] = str(exc)

    def location(prefix: str) -> Callable[[str], dict[str, Any]]:
        def parse(raw: str) -> dict[str, Any]:
            loc = parse_location(raw)
            return {f"{prefix}_city": loc.city, f"{prefix}_state": loc.state, f"{prefix}_zip": loc.zip_code}

        return parse

    def freight(raw: str) -> dict[str, Any]:
        for ft in ctx.company.enabled_freight_types:
            if raw.lower() in (ft.label.lower(), ft.key):
                return {"freight_type": ft.label}
        raise ValidationError("Choose a freight type from the list.")

    check("fullName", lambda v: {"full_name": parse_full_name(v)}, required=True, missing="Enter your full name.")
    check("companyName", lambda v: {"company_name": parse_company(v)}, required=False, missing="")
    check("email", lambda v: {"email": parse_email(v)}, required=True, missing="Enter your business email.")
    check("phone", lambda v: {"phone": parse_phone(v)}, required=True, missing="Enter a phone number.")
    check("pickupLocation", location("pickup"), required=True, missing="Enter the pickup city and state.")
    check("deliveryLocation", location("delivery"), required=True, missing="Enter the delivery city and state.")
    check(
        "pickupDate",
        lambda v: {"pickup_date": parse_pickup_date(v, ctx.today())},
        required=True,
        missing="Choose a pickup date.",
    )
    check("freightType", freight, required=True, missing="Choose a freight type.")
    check("estimatedWeight", lambda v: {"estimated_weight_lb": parse_weight(v)}, required=False, missing="")
    check("details", lambda v: {"shipment_details": parse_details(v)}, required=False, missing="")

    if errors:
        return errors, None
    try:
        return {}, QuoteDraft(**values)
    except PydanticValidationError:
        return {"form": "Some details are invalid. Please check the form and try again."}, None


async def post_quote(request: web.Request) -> web.Response:
    ctx, bot = request.app[CTX], request.app[BOT]
    origin = request.headers.get("Origin")
    if not _origin_allowed(ctx, origin):
        log.warning("website quote rejected: origin not allowed")
        return web.json_response({"ok": False, "error": "origin_not_allowed"}, status=403)

    ip = _client_ip(request, ctx.settings.web_trust_proxy)
    if not request.app[FLOOD_LIMITER].hit(ip):
        return _json({"ok": False, "error": "rate_limited"}, 429, origin)
    if request.content_type != "application/json":
        return _json({"ok": False, "error": "unsupported_media_type"}, 415, origin)
    try:
        payload = await request.json()
    except ValueError:
        return _json({"ok": False, "error": "invalid_json"}, 400, origin)
    if not isinstance(payload, dict):
        return _json({"ok": False, "error": "invalid_json"}, 400, origin)

    if payload.get("website"):  # honeypot field — invisible to people, filled by bots
        log.info("website quote rejected: honeypot")
        return _json({"ok": False, "error": "rejected"}, 400, origin)

    errors, draft = validate_website_payload(payload, ctx)
    if errors or draft is None:
        return _json({"ok": False, "errors": errors}, 422, origin)

    if not request.app[SAVE_LIMITER].hit(ip):
        return _json({"ok": False, "error": "rate_limited"}, 429, origin)

    key = payload.get("submissionKey")
    try:
        key = str(uuid.UUID(str(key)))
    except ValueError:
        key = str(uuid.uuid4())  # no idempotency key supplied

    try:
        result = await ctx.quotes.submit(
            telegram_user_id=None,
            draft=draft,
            submission_key=key,
            now=ctx.now(),
            today=ctx.today(),
            source=RequestSource.WEBSITE,
        )
    except PickupDateInPast:
        return _json({"ok": False, "errors": {"pickupDate": "Choose today or a later date."}}, 422, origin)
    except PermissionError:
        return _json({"ok": False, "error": "conflict"}, 409, origin)
    except Exception as exc:
        # Nothing was saved; the website shows its failure state and contact details.
        log.error("website quote submission failed", extra={"error": type(exc).__name__})
        return _json({"ok": False, "error": "unavailable"}, 503, origin)

    if result.created:
        ctx.spawn(
            ctx.notifications.dispatch(bot, now=ctx.now(), request_id=result.request_id),
            name=f"notify:{result.public_request_id}",
        )
    return _json({"ok": True, "requestId": result.public_request_id}, 201 if result.created else 200, origin)


async def preflight(request: web.Request) -> web.Response:
    origin = request.headers.get("Origin")
    if not origin or not _origin_allowed(request.app[CTX], origin):
        return web.Response(status=403)
    return web.Response(status=204, headers={**CORS_HEADERS, "Access-Control-Allow-Origin": origin, "Vary": "Origin"})


async def healthz(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


@web.middleware
async def _errors(request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
    try:
        return await handler(request)
    except web.HTTPRequestEntityTooLarge:
        return web.json_response({"ok": False, "error": "too_large"}, status=413)
    except web.HTTPException:
        raise
    except Exception as exc:  # never leak internals
        log.error("web handler error", extra={"error": type(exc).__name__})
        return web.json_response({"ok": False, "error": "internal"}, status=500)


def create_web_app(ctx: AppContext, bot: Bot) -> web.Application:
    app = web.Application(client_max_size=MAX_BODY_BYTES, middlewares=[_errors])
    app[CTX] = ctx
    app[BOT] = bot
    app[SAVE_LIMITER] = SlidingWindowLimiter(ctx.settings.website_quotes_per_hour_per_ip, window_seconds=3600)
    app[FLOOD_LIMITER] = SlidingWindowLimiter(30, window_seconds=600)
    app.router.add_post("/api/quote", post_quote)
    app.router.add_route("OPTIONS", "/api/quote", preflight)
    app.router.add_get("/healthz", healthz)
    return app


async def start_web_server(ctx: AppContext, bot: Bot) -> web.AppRunner:
    runner = web.AppRunner(create_web_app(ctx, bot), access_log=None)  # access logs would include client IPs
    await runner.setup()
    site = web.TCPSite(runner, ctx.settings.web_host, ctx.settings.web_port)
    await site.start()
    if not ctx.settings.website_allowed_origins and not ctx.settings.is_development:
        log.warning("WEBSITE_ALLOWED_ORIGINS is empty: browsers cannot submit the website form")
    log.info("website quote endpoint listening", extra={"host": ctx.settings.web_host, "port": ctx.settings.web_port})
    return runner
