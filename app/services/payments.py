"""Payment layer.

The application never talks to a gateway directly: it asks the configured
provider for a `CheckoutLink`. Swapping gateways — or plugging in Caixa's own
Pix/boleto API later — means writing one class here and changing one
environment variable. Nothing else in the system moves.

Providers:
  * MockProvider   — development, returns an internal fake checkout.
  * ManualProvider — a fixed payment link created in the bank's portal.
  * AsaasProvider  — recurring subscription, settling into the Caixa account.
"""

from __future__ import annotations

import hmac
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from ..config import settings
from ..models import Member
from ..plans import Plan

log = logging.getLogger("ccpa.payments")


@dataclass
class CheckoutLink:
    url: str
    external_reference: str | None
    provider: str


class PaymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_charge(self, member: Member, plan: Plan) -> CheckoutLink: ...

    def verify_webhook(self, headers: dict, body: bytes) -> bool:  # noqa: ARG002
        return True

    def parse_event(self, payload: dict) -> tuple[str | None, str | None]:
        """Return (external_reference, normalised status)."""
        return None, None


class MockProvider(PaymentProvider):
    """Fake checkout so the whole flow can be demonstrated before any contract
    with a bank or gateway exists."""

    name = "mock"

    def create_charge(self, member: Member, plan: Plan) -> CheckoutLink:
        return CheckoutLink(
            url=f"{settings.base_url}/pagamento/simulado/{member.id}",
            external_reference=f"mock_{member.id[:8]}",
            provider=self.name,
        )


class ManualProvider(PaymentProvider):
    """A single fixed payment link for everyone.

    Fastest to launch and the most laborious to run: nobody confirms the
    payment automatically, so someone reconciles the bank statement by hand.
    """

    name = "manual"

    def create_charge(self, member: Member, plan: Plan) -> CheckoutLink:
        if not settings.payment_static_link:
            raise RuntimeError("PAYMENT_STATIC_LINK is not configured.")
        return CheckoutLink(
            url=settings.payment_static_link,
            external_reference=None,
            provider=self.name,
        )


class AsaasProvider(PaymentProvider):
    """Recurring subscription through Asaas, with the money transferred to the
    association's account at Caixa Econômica Federal."""

    name = "asaas"
    _STATUS_MAP = {
        "PAYMENT_CONFIRMED": "CONFIRMED",
        "PAYMENT_RECEIVED": "CONFIRMED",
        "PAYMENT_OVERDUE": "FAILED",
        "PAYMENT_DELETED": "FAILED",
        "PAYMENT_REFUNDED": "REFUNDED",
    }

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=settings.asaas_base_url,
            headers={
                "access_token": settings.asaas_api_key,
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    def create_charge(self, member: Member, plan: Plan) -> CheckoutLink:
        from datetime import date, timedelta

        with self._client() as client:
            customer = client.post(
                "/customers",
                json={
                    "name": member.name,
                    "email": member.email,
                    "cpfCnpj": member.document,
                    "mobilePhone": member.mobile,
                    "postalCode": member.postal_code,
                    "externalReference": member.id,
                },
            )
            customer.raise_for_status()
            customer_id = customer.json()["id"]

            subscription = client.post(
                "/subscriptions",
                json={
                    "customer": customer_id,
                    # UNDEFINED lets the member pick Pix, boleto or card at
                    # checkout instead of us guessing for them.
                    "billingType": "UNDEFINED",
                    "value": plan.amount_cents / 100,
                    "cycle": "MONTHLY" if plan.cycle == "MONTHLY" else "YEARLY",
                    "description": f"Associação CCPA — {plan.name}",
                    "nextDueDate": (date.today() + timedelta(days=3)).isoformat(),
                    "externalReference": member.id,
                },
            )
            subscription.raise_for_status()
            sub = subscription.json()

            charges = client.get("/payments", params={"subscription": sub["id"]})
            charges.raise_for_status()
            items = charges.json().get("data", [])
            url = items[0]["invoiceUrl"] if items else sub.get("invoiceUrl", "")

        return CheckoutLink(url=url, external_reference=sub["id"], provider=self.name)

    def verify_webhook(self, headers: dict, body: bytes) -> bool:  # noqa: ARG002
        token = headers.get("asaas-access-token", "")
        if not settings.asaas_webhook_token:
            log.warning("ASAAS_WEBHOOK_TOKEN is empty — webhook not verified.")
            # Tolerated in development, never in production: an unverified
            # webhook lets anyone mark a membership as paid.
            return not settings.is_prod
        return hmac.compare_digest(token, settings.asaas_webhook_token)

    def parse_event(self, payload: dict) -> tuple[str | None, str | None]:
        event = payload.get("event", "")
        payment = payload.get("payment", {}) or {}
        reference = payment.get("subscription") or payment.get("externalReference")
        return reference, self._STATUS_MAP.get(event)


_PROVIDERS: dict[str, type[PaymentProvider]] = {
    "mock": MockProvider,
    "manual": ManualProvider,
    "asaas": AsaasProvider,
}


def get_payment_provider() -> PaymentProvider:
    return _PROVIDERS.get(settings.payment_provider, MockProvider)()
