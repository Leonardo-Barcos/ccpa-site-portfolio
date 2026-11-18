"""Transactional e-mail through Resend's HTTP API."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from ..config import settings
from ..models import EmailLog
from ..paths import TEMPLATES_DIR

log = logging.getLogger("ccpa.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render(template: str, context: dict[str, Any]) -> str:
    return _env.get_template(f"emails/{template}.html").render(**context)


def send_email(
    db: Session,
    *,
    recipient: str,
    subject: str,
    template: str,
    context: dict[str, Any],
    member_id: str | None = None,
    copy_admin: bool = False,
) -> bool:
    """Render and send. Never raises.

    A failing mail provider must not roll back a signup the member already
    completed, so the error is recorded in `email_logs` and the caller carries
    on. That table is how you find out later that a member never got their
    payment link.
    """
    html = _render(template, context)
    payload: dict[str, Any] = {
        "from": settings.mail_from,
        "to": [recipient],
        "subject": subject,
        "html": html,
        "reply_to": settings.mail_reply_to,
    }
    if copy_admin and settings.mail_bcc_admin:
        payload["bcc"] = [settings.mail_bcc_admin]

    entry = EmailLog(member_id=member_id, recipient=recipient, template=template)

    if not settings.resend_api_key:
        log.warning("RESEND_API_KEY missing — e-mail '%s' not sent.", template)
        entry.error = "RESEND_API_KEY not configured"
        db.add(entry)
        db.commit()
        return False

    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            timeout=15.0,
        )
        response.raise_for_status()
        entry.succeeded = True
        entry.provider_id = response.json().get("id")
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed to send e-mail '%s'", template)
        entry.error = str(exc)[:1000]
    finally:
        db.add(entry)
        db.commit()

    return entry.succeeded


def send_welcome_with_payment_link(db: Session, member, plan, checkout_url: str) -> bool:
    return send_email(
        db,
        recipient=member.email,
        subject=f"{member.first_name}, falta 1 passo para sua associação ao CCPA",
        template="welcome",
        context={
            "member": member,
            "plan": plan,
            "checkout_url": checkout_url,
            "cfg": settings,
        },
        member_id=member.id,
        copy_admin=True,
    )


def send_payment_confirmed(db: Session, member, plan) -> bool:
    return send_email(
        db,
        recipient=member.email,
        subject="Bem-vindo(a) ao Clube de Criativos do Pará!",
        template="payment_confirmed",
        context={"member": member, "plan": plan, "cfg": settings},
        member_id=member.id,
        copy_admin=True,
    )
