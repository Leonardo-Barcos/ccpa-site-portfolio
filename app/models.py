"""Database models."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# (str, Enum) rather than StrEnum is deliberate: SQLAlchemy stores the member
# value as text, which keeps the database readable and portable.
class EntityType(str, enum.Enum):
    PF = "PF"  # individual
    PJ = "PJ"  # company


class MemberStatus(str, enum.Enum):
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    ACTIVE = "ACTIVE"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("document", name="uq_member_document"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), index=True)
    plan_code: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus), default=MemberStatus.AWAITING_PAYMENT, index=True
    )

    # Identity. For individuals: full name and CPF. For companies: legal name
    # and CNPJ. One column pair serves both so the member list stays a single
    # table instead of two that have to be unioned on every query.
    name: Mapped[str] = mapped_column(String(180))
    trade_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    document: Mapped[str | None] = mapped_column(String(14), nullable=True, index=True)
    id_card: Mapped[str | None] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state_registration: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city_registration: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Professional profile
    linkedin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(180), nullable=True)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    # Contact
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    secondary_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    secondary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Address
    postal_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address_extra: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Member area credentials
    login: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Consent trail. Brazil's data protection law (LGPD) expects the
    # organisation to be able to prove when and from where consent was given.
    accepted_terms: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_terms_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_terms_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    payments: Mapped[list[Payment]] = relationship(
        back_populates="member", cascade="all, delete-orphan"
    )

    @property
    def first_name(self) -> str:
        return (self.trade_name or self.name).split(" ")[0]


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(30))
    external_reference: Mapped[str | None] = mapped_column(
        String(120), nullable=True, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer)
    cycle: Mapped[str] = mapped_column(String(10), default="MONTHLY")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING, index=True
    )
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    member: Mapped[Member] = relationship(back_populates="payments")


class EmailLog(Base):
    """Audit trail for outgoing e-mail.

    Kept because a signup that never received its payment link is otherwise
    invisible: the member simply does not come back.
    """

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recipient: Mapped[str] = mapped_column(String(255))
    template: Mapped[str] = mapped_column(String(60))
    provider_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ==========================================================================
#  Editorial content
# ==========================================================================


class PostKind(str, enum.Enum):
    NEWS = "NEWS"
    COLUMN = "COLUMN"


class Post(Base):
    """A news item or an opinion column.

    The kind splits the two site sections without duplicating the model, the
    admin screens or the queries.
    """

    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[PostKind] = mapped_column(Enum(PostKind), index=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(320))
    body: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(320))
    description: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    venue: Mapped[str] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    signup_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    free: Mapped[bool] = mapped_column(Boolean, default=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ContactMessage(Base):
    """Submission from the public contact form."""

    __tablename__ = "contact_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subject: Mapped[str] = mapped_column(String(80))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class AdminUser(Base):
    """Someone allowed into the publishing dashboard."""

    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
