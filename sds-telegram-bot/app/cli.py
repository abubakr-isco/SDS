"""Operational commands: `python -m app.cli <command>`.

add-admin <telegram_id> [--name NAME]   create or re-activate an administrator
remove-admin <telegram_id>              deactivate an administrator (history is kept)
list-admins
set-setting <key> <value>               override a contact field (see CONTACT_SETTING_KEYS)
unset-setting <key>
retry-notifications                     resend pending admin notifications now
purge-expired [--dry-run]               apply the data retention policy
check-config                            validate .env and config/company.toml
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.company import load_company_config
from app.config import DatabaseSettings, Settings
from app.database.models import utcnow
from app.database.repositories import AdminRepository, SettingsRepository
from app.database.session import create_engine, create_session_factory
from app.services.contact import CONTACT_SETTING_KEYS
from app.services.retention import purge_expired


def _session_factory():
    engine = create_engine(DatabaseSettings().database_url.get_secret_value())  # type: ignore[call-arg]
    return engine, create_session_factory(engine)


async def add_admin(telegram_id: int, name: str | None) -> None:
    engine, sessions = _session_factory()
    async with sessions() as session, session.begin():
        admin = await AdminRepository(session).upsert(telegram_id, name, active=True)
        print(f"Administrator active: {admin.display_name} ({admin.telegram_user_id})")
    await engine.dispose()


async def remove_admin(telegram_id: int) -> None:
    engine, sessions = _session_factory()
    async with sessions() as session, session.begin():
        admin = await AdminRepository(session).get_by_telegram_id(telegram_id)
        if admin is None:
            print("No administrator with that Telegram ID.")
        else:
            admin.is_active = False
            print(f"Administrator deactivated: {admin.display_name} ({admin.telegram_user_id})")
            print("Note: also remove the ID from ADMIN_TELEGRAM_IDS, or it is re-activated on the next start.")
    await engine.dispose()


async def list_admins() -> None:
    engine, sessions = _session_factory()
    async with sessions() as session:
        for a in await AdminRepository(session).list_all():
            print(f"{a.telegram_user_id}\t{'active' if a.is_active else 'inactive'}\t{a.display_name}")
    await engine.dispose()


async def set_setting(key: str, value: str | None) -> None:
    if key not in CONTACT_SETTING_KEYS:
        print("Allowed keys: " + ", ".join(CONTACT_SETTING_KEYS), file=sys.stderr)
        raise SystemExit(2)
    engine, sessions = _session_factory()
    async with sessions() as session, session.begin():
        repo = SettingsRepository(session)
        if value is None:
            print("Removed." if await repo.unset(key) else "Not set.")
        else:
            await repo.set(key, value)
            print("Saved.")
    await engine.dispose()


async def retry_notifications() -> None:
    from app.bot import create_bot
    from app.context import AppContext
    from app.services.tracking import build_tracking_provider

    settings = Settings()  # type: ignore[call-arg]
    engine = create_engine(settings.database_url.get_secret_value())
    ctx = AppContext(
        settings=settings,
        company=load_company_config(settings.company_config_path),
        session_factory=create_session_factory(engine),
        tracking=build_tracking_provider(settings.tracking_provider),
    )
    bot = create_bot(settings.bot_token.get_secret_value())
    try:
        report = await ctx.notifications.dispatch(bot, now=utcnow())
        print(f"Sent: {report.sent}, failed: {report.failed}")
    finally:
        await bot.session.close()
        await engine.dispose()


async def purge(dry_run: bool) -> None:
    settings = Settings()  # type: ignore[call-arg]
    engine = create_engine(settings.database_url.get_secret_value())
    result = await purge_expired(
        create_session_factory(engine), retention_days=settings.data_retention_days, now=utcnow(), dry_run=dry_run
    )
    print(f"{'Would delete' if dry_run else 'Deleted'}: {result.requests} requests, {result.customers} customers")
    await engine.dispose()


def check_config() -> None:
    settings = Settings()  # type: ignore[call-arg]
    company = load_company_config(settings.company_config_path)
    print(f"Environment: {settings.environment}, timezone: {settings.timezone}")
    print(f"Admins from env: {len(settings.admin_telegram_ids)}")
    print(f"Enabled services: {', '.join(s.name for s in company.enabled_services) or 'none'}")
    missing = [k for k, v in company.contact.model_dump().items() if not v]
    print(f"Contact fields not configured: {', '.join(missing) or 'none'}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("add-admin")
    p.add_argument("telegram_id", type=int)
    p.add_argument("--name")
    sub.add_parser("remove-admin").add_argument("telegram_id", type=int)
    sub.add_parser("list-admins")
    p = sub.add_parser("set-setting")
    p.add_argument("key")
    p.add_argument("value")
    sub.add_parser("unset-setting").add_argument("key")
    sub.add_parser("retry-notifications")
    sub.add_parser("purge-expired").add_argument("--dry-run", action="store_true")
    sub.add_parser("check-config")
    args = parser.parse_args(argv)

    match args.command:
        case "add-admin":
            asyncio.run(add_admin(args.telegram_id, args.name))
        case "remove-admin":
            asyncio.run(remove_admin(args.telegram_id))
        case "list-admins":
            asyncio.run(list_admins())
        case "set-setting":
            asyncio.run(set_setting(args.key, args.value))
        case "unset-setting":
            asyncio.run(set_setting(args.key, None))
        case "retry-notifications":
            asyncio.run(retry_notifications())
        case "purge-expired":
            asyncio.run(purge(args.dry_run))
        case "check-config":
            check_config()


if __name__ == "__main__":
    main()
