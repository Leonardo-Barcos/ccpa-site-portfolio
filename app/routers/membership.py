"""Public signup: the two forms, the success page and the mock checkout."""

from __future__ import annotations

import logging
from datetime import UTC

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Member, MemberStatus, Payment, PaymentStatus
from ..plans import CHAPTERS, GENDERS, PLANS, STATES, plans_for
from ..schemas import CompanySignup, IndividualSignup
from ..security import client_ip
from ..services.members import BusinessError, register_signup
from ..templating import templates

log = logging.getLogger("ccpa.membership")
router = APIRouter()

BENEFIT_CARDS = [
    {
        "title": "Micro pesquisa",
        "text": "Avaliação inicial da empresa e do negócio, feita por quem conhece "
        "o mercado criativo paraense.",
        "color": "verde",
    },
    {
        "title": "Avaliação de projetos",
        "text": "Estudantes têm seus projetos avaliados por um profissional ativo "
        "no mercado.",
        "color": "vermelho",
    },
    {
        "title": "40% de desconto",
        "text": "No e-commerce do Clube de Criação do Rio de Janeiro, para todos "
        "os associados.",
        "color": "azul",
    },
    {
        "title": "Encontro mensal de negócios",
        "text": "Rodadas de networking e oportunidades reais entre estudantes, "
        "profissionais e empresas associadas.",
        "color": "amarelo",
    },
]


def _base_context(request: Request) -> dict:
    return {
        "request": request,
        "individual_plans": plans_for("PF"),
        "company_plans": plans_for("PJ"),
        "chapters": CHAPTERS,
        "genders": GENDERS,
        "states": STATES,
        "benefits": BENEFIT_CARDS,
    }


def _clean_form(form: dict) -> dict:
    """HTML sends empty fields as "".

    Dropping them lets Pydantic apply the declared default (None for optional
    fields) or report a missing required field, instead of trying to parse an
    empty string as a date or an e-mail.
    """
    cleaned = {}
    for key, value in form.items():
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                continue
        cleaned[key] = value
    return cleaned


# Pydantic reports in English; the visitor reads Portuguese.
_MESSAGE_MAP = (
    ("Field required", "Campo obrigatório."),
    ("valid email address", "E-mail inválido."),
    ("valid date", "Data inválida."),
    ("at least", "Valor muito curto."),
    ("at most", "Valor muito longo."),
    ("should be a valid", "Valor inválido."),
)


def _translate(message: str) -> str:
    message = message.replace("Value error, ", "")
    for fragment, translation in _MESSAGE_MAP:
        if fragment in message:
            return translation
    return message


def _field_errors(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for error in exc.errors():
        field = str(error["loc"][0]) if error["loc"] else "_general"
        errors.setdefault(field, _translate(error["msg"]))
    return errors


@router.get("/associe-se", response_class=HTMLResponse)
def signup_page(request: Request, tipo: str = "pf"):
    context = _base_context(request)
    context.update({"tab": "pj" if tipo == "pj" else "pf", "errors": {}, "form": {}})
    return templates.TemplateResponse(request, "membership.html", context)


def _handle_submission(
    request: Request, db: Session, form: dict, schema, tab: str
) -> HTMLResponse:
    try:
        data = schema(**_clean_form(form))
    except ValidationError as exc:
        context = _base_context(request)
        context.update({"tab": tab, "errors": _field_errors(exc), "form": form})
        return templates.TemplateResponse(
            request, "membership.html", context, status_code=422
        )

    try:
        member, _ = register_signup(db, data, ip=client_ip(request))
    except BusinessError as exc:
        context = _base_context(request)
        context.update({"tab": tab, "errors": {exc.field: exc.message}, "form": form})
        return templates.TemplateResponse(
            request, "membership.html", context, status_code=409
        )

    return RedirectResponse(f"/associe-se/sucesso/{member.id}", status_code=303)


@router.post("/associe-se/pf")
async def submit_individual(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    form["accepted_terms"] = form.get("accepted_terms") in ("on", "true", "1")
    return _handle_submission(request, db, form, IndividualSignup, "pf")


@router.post("/associe-se/pj")
async def submit_company(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    form["accepted_terms"] = form.get("accepted_terms") in ("on", "true", "1")
    return _handle_submission(request, db, form, CompanySignup, "pj")


@router.get("/associe-se/sucesso/{member_id}", response_class=HTMLResponse)
def signup_success(request: Request, member_id: str, db: Session = Depends(get_db)):
    member = db.get(Member, member_id)
    if not member:
        return RedirectResponse("/associe-se", status_code=302)

    payment = (
        db.query(Payment)
        .filter(Payment.member_id == member.id)
        .order_by(Payment.created_at.desc())
        .first()
    )
    return templates.TemplateResponse(
        request,
        "success.html",
        {
            "request": request,
            "member": member,
            "plan": PLANS[member.plan_code],
            "payment": payment,
        },
    )


@router.get("/pagamento/simulado/{member_id}", response_class=HTMLResponse)
def mock_checkout(request: Request, member_id: str, db: Session = Depends(get_db)):
    """Fake checkout screen. Only reachable with PAYMENT_PROVIDER=mock."""
    from ..config import settings

    if settings.payment_provider != "mock":
        return RedirectResponse("/associe-se", status_code=302)

    member = db.get(Member, member_id)
    if not member:
        return RedirectResponse("/associe-se", status_code=302)

    return templates.TemplateResponse(
        request,
        "mock_payment.html",
        {"request": request, "member": member, "plan": PLANS[member.plan_code]},
    )


@router.post("/pagamento/simulado/{member_id}/confirmar")
def confirm_mock_payment(member_id: str, db: Session = Depends(get_db)):
    from datetime import datetime

    from ..config import settings
    from ..services.email import send_payment_confirmed

    if settings.payment_provider != "mock":
        return RedirectResponse("/associe-se", status_code=302)

    member = db.get(Member, member_id)
    if not member:
        return RedirectResponse("/associe-se", status_code=302)

    payment = (
        db.query(Payment)
        .filter(Payment.member_id == member.id)
        .order_by(Payment.created_at.desc())
        .first()
    )
    if payment:
        payment.status = PaymentStatus.CONFIRMED
        payment.paid_at = datetime.now(UTC)
    member.status = MemberStatus.ACTIVE
    db.commit()

    send_payment_confirmed(db, member, PLANS[member.plan_code])
    return RedirectResponse(f"/associe-se/sucesso/{member.id}", status_code=303)
