"""website quote requests: request source, customers without Telegram

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("customers", "telegram_user_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=False)
    op.add_column(
        "quote_requests",
        sa.Column(
            "source",
            sa.Enum(
                "telegram",
                "website",
                name="request_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            server_default="telegram",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("quote_requests", "source")  # also drops its CHECK constraint
    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    # Website customers have no Telegram ID and cannot be represented in the old schema.
    op.execute("DELETE FROM customers WHERE telegram_user_id IS NULL")
    op.alter_column("customers", "telegram_user_id", existing_type=sa.BigInteger(), nullable=False)
