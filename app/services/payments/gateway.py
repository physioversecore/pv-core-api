from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Canonical payment lifecycle statuses (stored in Payment.status).
PENDING = "PENDING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"
REFUNDED = "REFUNDED"

# Payment methods that go through a live gateway. Anything outside this set
# falls back to the manual (cash-on-visit / off-gateway) path, which keeps the
# legacy behaviour of marking the payment COMPLETED on booking.
# NOTE: connectips is method-gated here for Phase 2 — until the NCHL rail is
# implemented it must NOT be in this tuple or bookings are left PENDING with a
# gateway that doesn't exist.
GATEWAY_METHODS = ("esewa", "khalti")

# Rationalised variants of a few "national" methods that share a gateway rail.
# Khalti/IME are merged (Khalti by IME), so both route to the khalti gateway.
_METHOD_ALIASES = {
    "imepay": "khalti",
}


def is_gateway_method(method: str) -> bool:
    return normalize_method(method) in GATEWAY_METHODS


def normalize_method(method: str) -> str:
    """Lowercase, alias-ised method key used to look up a gateway."""
    m = (method or "").strip().lower()
    return _METHOD_ALIASES.get(m, m)


class GatewayError(Exception):
    """A gateway responded with an error we did not expect."""


class GatewayConfigError(Exception):
    """The gateway is not configured (missing env vars / credentials)."""

    def __init__(self, message: str):
        super().__init__(message)


@dataclass
class GatewayInitiation:
    """What the client needs to start a payment on the gateway's page.

    type:
      - "redirect"  -> client navigates to `url` (hosted checkout)
      - "form"      -> client auto-submits an HTML form to `url` with `form_fields`
      - "manual"    -> no outbound payment (cash / off-gateway); booking is final
    """

    type: str
    url: str | None = None
    form_fields: dict[str, Any] | None = field(default_factory=dict)
    expires_at: datetime | None = None


@dataclass
class GatewayVerification:
    """Result of a server-side verification call against the gateway."""

    status: str
    ref: str | None = None
    detail: str | None = None


class PaymentGateway:
    """Common interface every rail implements. `db` is passed in so a gateway
    can persist its own references (e.g. Khalti's pidx in transactionRef)."""

    name: str = "manual"

    async def initiate(self, db, payment, payload: dict) -> GatewayInitiation:
        raise NotImplementedError

    async def verify(self, db, payment, params: dict) -> GatewayVerification:
        raise NotImplementedError