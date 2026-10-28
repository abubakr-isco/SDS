from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CompanySetting


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def all(self) -> dict[str, str]:
        rows = await self.session.scalars(select(CompanySetting))
        return {row.setting_key: row.setting_value for row in rows}

    async def set(self, key: str, value: str) -> None:
        row = await self.session.scalar(select(CompanySetting).where(CompanySetting.setting_key == key))
        if row is None:
            self.session.add(CompanySetting(setting_key=key, setting_value=value))
        else:
            row.setting_value = value
        await self.session.flush()

    async def unset(self, key: str) -> bool:
        result = await self.session.execute(delete(CompanySetting).where(CompanySetting.setting_key == key))
        return bool(result.rowcount)
