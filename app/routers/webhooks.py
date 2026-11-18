"""Payment confirmation callback from the gateway."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Member, MemberStatus, Payment, PaymentStatus
from ..plans import PLANS
from ..services.email import send_payment_confirmed
from ..services.payments import get_payment_provider

log = logging.getLogger("ccpa.webhook")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_TRANSITIONS = {
    "CONFIRMED": (PaymentStatus.CONFIRMED, MemberStatus.ACTIVE),
    "FAILED": (PaymentStatus.FAILED, MemberStatus.OVERDUE),
    "REFUNDED": (PaymentStatus.REFUNDED, MemberStatus.CANCELLED),
}


@router.post("/pagamento")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    provider = get_payment_provider()

    if not provider.verify_webhook(dict(request.headers), body):
        log.warning("Webhook rejected: bad signature or token.")
        raise HTTPException(status_code=401, detail="Invalid signature.")

    payload = await request.json()
    reference, status = provider.parse_event(payload)

    if not reference or not status:
        return {"ok": True, "ignored": True}

    payment = (
        db.query(Payment)
        .filter(Payment.external_reference == reference)
        .order_by(Payment.created_at.desc())
        .first()
    )
    if not payment:
        log.warning("Webhook for unknown reference: %s", reference)
        return {"ok": True, "ignored": True}

    new_payment_status, new_member_status = _TRANSITIONS[status]

    # Idempotency. Gateways retry, and a replayed event must not send the
    # welcome e-mail twice.
    if payment.status == new_payment_status:
        return {"ok": True, "duplicate": True}

    payment.status = new_payment_status
    if new_payment_status == PaymentStatus.CONFIRMED:
        payment.paid_at = datetime.now(UTC)

    member = db.get(Member, payment.member_id)
    if member:
        member.status = new_member_status
    db.commit()

    if member and new_payment_status == PaymentStatus.CONFIRMED:
        send_payment_confirmed(db, member, PLANS[member.plan_code])

    return {"ok": True}
