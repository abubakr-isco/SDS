from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Administrator


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, telegram_user_id: int) -> Administrator | None:
        return await self.session.scalar(
            select(Administrator).where(
                Administrator.telegram_user_id == telegram_user_id, Administrator.is_active.is_(True)
            )
        )

    async def get_by_telegram_id(self, telegram_user_id: int) -> Administrator | None:
        return await self.session.scalar(
            select(Administrator).where(Administrator.telegram_user_id == telegram_user_id)
        )

    async def get(self, admin_id: int) -> Administrator | None:
        return await self.session.get(Administrator, admin_id)

    async def list_active(self) -> Sequence[Administrator]:
        result = await self.session.scalars(
            select(Administrator).where(Administrator.is_active.is_(True)).order_by(Administrator.id)
        )
        return result.all()

    async def list_all(self) -> Sequence[Administrator]:
        return (await self.session.scalars(select(Administrator).order_by(Administrator.id))).all()

    async def upsert(
        self, telegram_user_id: int, display_name: str | None = None, active: bool = True
    ) -> Administrator:
        admin = await self.get_by_telegram_id(telegram_user_id)
        if admin is None:
            admin = Administrator(
                telegram_user_id=telegram_user_id,
                display_name=display_name or f"Admin {telegram_user_id}",
                is_active=active,
            )
            self.session.add(admin)
        else:
            admin.is_active = active
            if display_name:
                admin.display_name = display_name
        await self.session.flush()
        return admin
