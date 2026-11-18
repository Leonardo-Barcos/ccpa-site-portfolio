"""Business rules for joining the association."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import EntityType, Member, MemberStatus, Payment, PaymentStatus
from ..plans import PLANS, Plan
from ..schemas import CompanySignup, IndividualSignup
from ..security import hash_password
from .email import send_welcome_with_payment_link
from .payments import get_payment_provider


class BusinessError(Exception):
    """An expected failure shown back on the form, next to the offending field."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(message)


def _reject_duplicates(
    db: Session, *, email: str, login: str, document: str | None
) -> None:
    if db.scalar(
        select(func.count())
        .select_from(Member)
        .where(func.lower(Member.login) == login.lower())
    ):
        raise BusinessError("login", "Este login já está em uso.")

    if db.scalar(
        select(func.count())
        .select_from(Member)
        .where(func.lower(Member.email) == email.lower())
    ):
        raise BusinessError(
            "email", "Já existe uma associação com este e-mail. Fale conosco."
        )

    if document and db.scalar(
        select(func.count()).select_from(Member).where(Member.document == document)
    ):
        raise BusinessError("document", "Este CPF/CNPJ já está cadastrado.")


def _shared_fields(data) -> dict:
    return {
        "mobile": data.mobile,
        "secondary_phone": data.secondary_phone,
        "email": str(data.email),
        "secondary_email": str(data.secondary_email) if data.secondary_email else None,
        "postal_code": data.postal_code,
        "street": data.street,
        "number": data.number,
        "district": data.district,
        "state": data.state,
        "city": data.city,
        "address_extra": data.address_extra,
        "login": data.login,
        "password_hash": hash_password(data.password),
        "accepted_terms": data.accepted_terms,
    }


def build_member(data: IndividualSignup | CompanySignup) -> Member:
    shared = _shared_fields(data)

    if isinstance(data, IndividualSignup):
        return Member(
            entity_type=EntityType.PF,
            plan_code=data.plan_code,
            name=data.name,
            document=data.cpf,
            id_card=data.id_card,
            birth_date=data.birth_date.isoformat() if data.birth_date else None,
            gender=data.gender,
            linkedin=data.linkedin,
            company=data.company,
            role=data.role,
            chapter=data.chapter,
            **shared,
        )

    return Member(
        entity_type=EntityType.PJ,
        plan_code=data.plan_code,
        name=data.legal_name,
        trade_name=data.trade_name,
        document=data.cnpj,
        state_registration=data.state_registration,
        city_registration=data.city_registration,
        chapter=data.chapter,
        website=data.website,
        **shared,
    )


def register_signup(
    db: Session,
    data: IndividualSignup | CompanySignup,
    *,
    ip: str | None = None,
) -> tuple[Member, Payment]:
    """Create the member, open the charge and send the payment link."""
    document = getattr(data, "cpf", None) or getattr(data, "cnpj", None)
    _reject_duplicates(db, email=str(data.email), login=data.login, document=document)

    member = build_member(data)
    member.accepted_terms_ip = ip
    member.accepted_terms_at = datetime.now(UTC)
    member.status = MemberStatus.AWAITING_PAYMENT

    db.add(member)
    db.flush()  # assigns the id without committing yet

    plan: Plan = PLANS[member.plan_code]
    link = get_payment_provider().create_charge(member, plan)

    payment = Payment(
        member_id=member.id,
        provider=link.provider,
        external_reference=link.external_reference,
        amount_cents=plan.amount_cents,
        cycle=plan.cycle,
        status=PaymentStatus.PENDING,
        checkout_url=link.url,
    )
    db.add(payment)
    db.commit()
    db.refresh(member)
    db.refresh(payment)

    send_welcome_with_payment_link(db, member, plan, link.url)
    return member, payment
