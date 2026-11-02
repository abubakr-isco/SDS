"""Full SMS consent record for website requests: yes/no flag, source, wording version and exact text

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quote_requests", sa.Column("sms_consent", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("quote_requests", sa.Column("sms_consent_source", sa.String(length=40), nullable=True))
    op.add_column("quote_requests", sa.Column("sms_consent_version", sa.String(length=32), nullable=True))
    op.add_column("quote_requests", sa.Column("sms_consent_text", sa.Text(), nullable=True))
    # Requests saved before this revision recorded consent only as a timestamp.
    op.execute("UPDATE quote_requests SET sms_consent = TRUE WHERE sms_consent_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column("quote_requests", "sms_consent_text")
    op.drop_column("quote_requests", "sms_consent_version")
    op.drop_column("quote_requests", "sms_consent_source")
    op.drop_column("quote_requests", "sms_consent")
