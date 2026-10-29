"""SMS consent from the website form: timestamp and phone number of the opt-in

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quote_requests", sa.Column("sms_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quote_requests", sa.Column("sms_consent_phone", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("quote_requests", "sms_consent_phone")
    op.drop_column("quote_requests", "sms_consent_at")
