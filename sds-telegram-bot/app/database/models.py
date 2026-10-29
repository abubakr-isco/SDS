from __future__ import annotations

import enum
from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# BIGINT on PostgreSQL; INTEGER on SQLite so autoincrement works in tests.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class QuoteStatus(enum.StrEnum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    AWAITING_CUSTOMER = "awaiting_customer_info"
    QUOTED = "quoted"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return STATUS_LABELS[self]


STATUS_LABELS: dict[QuoteStatus, str] = {
    QuoteStatus.NEW: "New",
    QuoteStatus.UNDER_REVIEW: "Under Review",
    QuoteStatus.AWAITING_CUSTOMER: "Awaiting Customer Information",
    QuoteStatus.QUOTED: "Quoted",
    QuoteStatus.ACCEPTED: "Accepted",
    QuoteStatus.IN_PROGRESS: "In Progress",
    QuoteStatus.COMPLETED: "Completed",
    QuoteStatus.CANCELLED: "Cancelled",
}

CLOSED_STATUSES = (QuoteStatus.COMPLETED, QuoteStatus.CANCELLED)


class EventType(enum.StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    NOTE_ADDED = "note_added"
    ASSIGNED = "assigned"
    CUSTOMER_NOTIFIED = "customer_notified"
    CUSTOMER_MESSAGED = "customer_messaged"


class RequestSource(enum.StrEnum):
    TELEGRAM = "telegram"
    WEBSITE = "website"


class NotificationStatus(enum.StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    # Stored as VARCHAR + CHECK constraint (no native PG enum) so adding a status is a simple migration.
    return Enum(
        cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
        create_constraint=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), onupdate=utcnow, nullable=False
    )


class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    # NULL for customers who submitted through the website form (no Telegram account linked).
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)

    quote_requests: Mapped[list[QuoteRequest]] = relationship(back_populates="customer", passive_deletes=True)


class QuoteRequest(TimestampMixin, Base):
    __tablename__ = "quote_requests"
    __table_args__ = (Index("ix_quote_requests_status_created_at", "status", "created_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    public_request_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # Idempotency key generated when the review screen is shown; blocks duplicate submissions.
    submission_key: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[RequestSource] = mapped_column(
        _enum(RequestSource, "request_source"),
        nullable=False,
        default=RequestSource.TELEGRAM,
        server_default=RequestSource.TELEGRAM.value,
    )
    requested_service: Mapped[str | None] = mapped_column(String(60))
    pickup_city: Mapped[str] = mapped_column(String(80), nullable=False)
    pickup_state: Mapped[str] = mapped_column(String(2), nullable=False)
    pickup_zip: Mapped[str | None] = mapped_column(String(10))
    delivery_city: Mapped[str] = mapped_column(String(80), nullable=False)
    delivery_state: Mapped[str] = mapped_column(String(2), nullable=False)
    delivery_zip: Mapped[str | None] = mapped_column(String(10))
    pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    freight_type: Mapped[str] = mapped_column(String(40), nullable=False)
    estimated_weight_lb: Mapped[int | None] = mapped_column(Integer)
    shipment_details: Mapped[str | None] = mapped_column(Text)
    # Proof of SMS opt-in from the website form: when it was given and for which number. NULL = no consent.
    sms_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sms_consent_phone: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[QuoteStatus] = mapped_column(
        _enum(QuoteStatus, "quote_status"),
        nullable=False,
        default=QuoteStatus.NEW,
        server_default=QuoteStatus.NEW.value,
    )
    assigned_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("administrators.id", ondelete="SET NULL"), index=True
    )

    customer: Mapped[Customer] = relationship(back_populates="quote_requests")
    assigned_admin: Mapped[Administrator | None] = relationship()
    events: Mapped[list[QuoteRequestEvent]] = relationship(
        back_populates="quote_request", passive_deletes=True, order_by="QuoteRequestEvent.id"
    )


class QuoteRequestEvent(Base):
    __tablename__ = "quote_request_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    quote_request_id: Mapped[int] = mapped_column(
        ForeignKey("quote_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[EventType] = mapped_column(_enum(EventType, "event_type"), nullable=False)
    previous_status: Mapped[QuoteStatus | None] = mapped_column(_enum(QuoteStatus, "previous_status"))
    new_status: Mapped[QuoteStatus] = mapped_column(_enum(QuoteStatus, "new_status"), nullable=False)
    # NULL means the customer or the system (e.g. request creation).
    changed_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("administrators.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    quote_request: Mapped[QuoteRequest] = relationship(back_populates="events")
    changed_by: Mapped[Administrator | None] = relationship()


class CompanySetting(Base):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), onupdate=utcnow, nullable=False
    )


class QuoteRequestCounter(Base):
    """Per-year sequence behind public request IDs (SDS-Q-2026-0001)."""

    __tablename__ = "quote_request_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class AdminNotification(TimestampMixin, Base):
    """Outbox row: one per (request, administrator). Written in the same transaction as the request."""

    __tablename__ = "admin_notifications"
    __table_args__ = (
        UniqueConstraint("quote_request_id", "administrator_id", name="uq_admin_notifications_request_admin"),
        Index("ix_admin_notifications_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    quote_request_id: Mapped[int] = mapped_column(ForeignKey("quote_requests.id", ondelete="CASCADE"), nullable=False)
    administrator_id: Mapped[int] = mapped_column(ForeignKey("administrators.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        _enum(NotificationStatus, "notification_status"), nullable=False, default=NotificationStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    quote_request: Mapped[QuoteRequest] = relationship()
    administrator: Mapped[Administrator] = relationship()
