"""Contact details: config/company.toml, optionally overridden by company_settings rows."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.company import CompanyConfig, ContactInfo
from app.database.repositories import SettingsRepository

# company_settings keys that may override the TOML contact fields.
CONTACT_SETTING_KEYS = {
    "contact.phone": "phone",
    "contact.email": "email",
    "contact.website": "website",
    "contact.office_hours": "office_hours",
    "contact.office_address": "office_address",
}


async def load_contact(company: CompanyConfig, session_factory: async_sessionmaker[AsyncSession]) -> ContactInfo:
    data = company.contact.model_dump(mode="json")
    try:
        async with session_factory() as session:
            overrides = await SettingsRepository(session).all()
    except Exception:
        # Contact info must stay reachable even if the database is down.
        overrides = {}
    for key, field in CONTACT_SETTING_KEYS.items():
        if key in overrides:
            data[field] = overrides[key]
    return ContactInfo.model_validate(data)
