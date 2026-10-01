import logging

import httpx

from app import settings

from .gateway import (
    CANCELLED,
    COMPLETED,
    FAILED,
    PENDING,
    GatewayConfigError,
    GatewayError,
    GatewayInitiation,
    GatewayVerification,
    PaymentGateway,
)

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "test": "https://dev.khalti.com/api/v2/",
    "live": "https://khalti.com/api/v2/",
}

# Khalti lookup treats exactly these as conclusive failures.
_FAILED_STATUSES = {"Canceled", "Cancelled", "Expired", "Failed"}


def _base_url(env: str) -> str:
    return _BASE_URLS.get(env, _BASE_URLS["test"])


class KhaltiGateway(PaymentGateway):
    name = "khalti"

    def _auth_headers(self) -> dict:
        key = settings.khalti_secret_key
        if not key:
            raise GatewayConfigError(
                "Khalti is not configured — add KHALTI_SECRET_KEY to pvc-api/.env"
            )
        return {"Authorization": f"Key {key}"}

    async def initiate(self, db, payment, payload: dict) -> GatewayInitiation:
        headers = self._auth_headers()
        customer = payload.get("customer") or {}

        body = {
            "return_url": settings.khalti_return_url,
            "website_url": settings.app_public_url,
            "amount": int(round(payment.amount * 100)),  # NPR -> paisa
            "purchase_order_id": f"pymt-{payment.id}",
            "purchase_order_name": "Home physio session",
            "customer_info": {
                "name": customer.get("name") or "Patient",
                "email": customer.get("email") or "",
                "phone": customer.get("phone") or "",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    _base_url(settings.khalti_env) + "epayment/initiate/",
                    json=body,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise GatewayError(f"Khalti initiate network error: {exc}")

        if resp.status_code not in (200, 201):
            detail = resp.json().get("detail") if resp.content else resp.text
            raise GatewayError(f"Khalti initiate failed ({resp.status_code}): {detail}")

        data = resp.json()
        pidx = data.get("pidx")
        if not pidx:
            raise GatewayError(f"Khalti initiate returned no pidx: {data}")

        # Persist pidx so a later lookup/status refresh can resolve this payment.
        await db.payment.update(
            where={"id": payment.id}, data={"transactionRef": pidx}
        )

        return GatewayInitiation(
            type="redirect",
            url=data.get("payment_url"),
            expires_at=None,
        )

    async def verify(self, db, payment, params: dict) -> GatewayVerification:
        headers = self._auth_headers()
        # Prefer the pidx from the callback; fall back to the one we stored at
        # initiate-time (supports silent status refreshes without a callback).
        pidx = params.get("pidx") or (payment.transactionRef or "")
        if not pidx:
            return GatewayVerification(FAILED, detail="Missing Khalti pidx")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    _base_url(settings.khalti_env) + "epayment/lookup/",
                    json={"pidx": pidx},
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise GatewayError(f"Khalti lookup network error: {exc}")

        if resp.status_code != 200:
            detail = resp.json().get("detail") if resp.content else resp.text
            raise GatewayError(f"Khalti lookup failed ({resp.status_code}): {detail}")

        data = resp.json()
        status = data.get("status", "")

        if status == "Completed":
            return GatewayVerification(
                COMPLETED, ref=data.get("transaction_id") or None
            )
        if status in _FAILED_STATUSES:
            return GatewayVerification(CANCELLED, detail=f"Khalti status: {status}")
        return GatewayVerification(PENDING, detail=f"Khalti status: {status}")