from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Customer


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> Customer | None:
        return await self.session.scalar(select(Customer).where(Customer.telegram_user_id == telegram_user_id))

    async def upsert(
        self, *, telegram_user_id: int, full_name: str, company_name: str | None, email: str, phone: str
    ) -> Customer:
        """Create the customer or refresh their contact details with the latest submission."""
        customer = await self.session.scalar(
            select(Customer).where(Customer.telegram_user_id == telegram_user_id).with_for_update()
        )
        if customer is None:
            customer = Customer(telegram_user_id=telegram_user_id)
            self.session.add(customer)
        customer.full_name = full_name
        customer.company_name = company_name
        customer.email = email
        customer.phone = phone
        await self.session.flush()
        return customer

    async def upsert_website(self, *, full_name: str, company_name: str | None, email: str, phone: str) -> Customer:
        """Website customers have no Telegram ID; the same email address maps to the same customer."""
        customer = await self.session.scalar(
            select(Customer)
            .where(Customer.telegram_user_id.is_(None), func.lower(Customer.email) == email.lower())
            .order_by(Customer.id)
            .limit(1)
            .with_for_update()
        )
        if customer is None:
            customer = Customer(telegram_user_id=None)
            self.session.add(customer)
        customer.full_name = full_name
        customer.company_name = company_name
        customer.email = email
        customer.phone = phone
        await self.session.flush()
        return customer
