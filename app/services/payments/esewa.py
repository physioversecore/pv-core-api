import base64
import hashlib
import hmac
import json
import logging

import httpx

from app import settings

from .gateway import (
    CANCELLED,
    COMPLETED,
    FAILED,
    PENDING,
    GatewayError,
    GatewayInitiation,
    GatewayVerification,
    PaymentGateway,
)

logger = logging.getLogger(__name__)

SIGNED_FIELD_NAMES = "total_amount,transaction_uuid,product_code"

_ENDPOINTS = {
    "uat": {
        "form": "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
        "status": "https://rc.esewa.com.np/api/epay/transaction/status/",
    },
    "prod": {
        "form": "https://epay.esewa.com.np/api/epay/main/v2/form",
        "status": "https://esewa.com.np/api/epay/transaction/status/",
    },
}


def _endpoints(env: str) -> dict:
    return _ENDPOINTS.get(env, _ENDPOINTS["uat"])


def _hmac_base64(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _build_signed_message(amount: float, txn_uuid: str, product_code: str) -> str:
    return (
        f"total_amount={amount},"
        f"transaction_uuid={txn_uuid},"
        f"product_code={product_code}"
    )


def _sign(amount: float, txn_uuid: str, product_code: str, secret: str) -> str:
    return _hmac_base64(_build_signed_message(amount, txn_uuid, product_code), secret)


def _verify_response_signature(data: dict, secret: str) -> bool:
    """Verify the HMAC signature eSewa puts on its success/status payload.

    eSewa signs every field listed in `signed_field_names`, concatenated in
    exactly that order as `field=value,field=value,...`, then base64-encodes
    the HMAC-SHA256 with the merchant secret.
    """
    supplied = data.get("signature") or ""
    field_names = [f.strip() for f in (data.get("signed_field_names") or "").split(",") if f.strip()]
    message = ",".join(f"{name}={data.get(name, '')}" for name in field_names)
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    try:
        actual = base64.b64decode(supplied)
    except Exception:
        return False
    return hmac.compare_digest(actual, expected)


def _decode_callback_data(raw: str) -> dict:
    """eSewa returns `?data=<base64>` of a JSON object. Decode it leniently."""
    padded = raw + "=" * (-len(raw) % 4)
    try:
        decoded = base64.b64decode(padded)
    except Exception:
        raise GatewayError("Could not decode eSewa callback payload")
    try:
        return json.loads(decoded)
    except Exception:
        raise GatewayError("eSewa callback payload is not valid JSON")


class EsewaGateway(PaymentGateway):
    name = "esewa"

    async def initiate(self, db, payment, payload: dict) -> GatewayInitiation:
        secret = settings.esewa_secret_key
        if not secret:
            raise GatewayConfigError(
                "eSewa is not configured — add ESEWA_SECRET_KEY to pvc-api/.env"
            )

        amount = int(round(payment.amount))
        txn_uuid = payment.id
        endpoints = _endpoints(settings.esewa_env)

        signature = _sign(amount, txn_uuid, settings.esewa_product_code, secret)

        form_fields = {
            "amount": str(amount),
            "tax_amount": "0",
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "product_code": settings.esewa_product_code,
            "transaction_uuid": txn_uuid,
            "signed_field_names": SIGNED_FIELD_NAMES,
            "signature": signature,
            "success_url": settings.esewa_success_url,
            "failure_url": settings.esewa_failure_url,
        }
        return GatewayInitiation(type="form", url=endpoints["form"], form_fields=form_fields)

    async def verify(self, db, payment, params: dict) -> GatewayVerification:
        secret = settings.esewa_secret_key
        if not secret:
            raise GatewayConfigError(
                "eSewa is not configured — add ESEWA_SECRET_KEY to pvc-api/.env"
            )

        raw = params.get("data")
        if not raw:
            return GatewayVerification(FAILED, detail="Missing eSewa callback data")

        data = _decode_callback_data(raw)

        if not _verify_response_signature(data, secret):
            return GatewayVerification(FAILED, detail="eSewa callback signature invalid")

        if data.get("status") != "COMPLETE":
            return GatewayVerification(CANCELLED, detail=f"eSewa status: {data.get('status')}")

        # Replay protection: the transaction_uuid we signed must match this payment.
        if data.get("transaction_uuid") != payment.id:
            return GatewayVerification(FAILED, detail="eSewa transaction_uuid mismatch")

        # Amount tamper detection against the stored booking.
        try:
            returned_amount = float(data.get("total_amount"))
        except (TypeError, ValueError):
            return GatewayVerification(FAILED, detail="eSewa total_amount invalid")
        if abs(returned_amount - payment.amount) > 0.01:
            return GatewayVerification(FAILED, detail="eSewa amount mismatch")

        # Defense-in-depth status check. Signed payload already passed, so a
        # transient failure of this best-effort check does not fail the payment.
        await self._status_check(payment)

        return GatewayVerification(
            COMPLETED, ref=data.get("transaction_code") or None
        )

    async def _status_check(self, payment) -> None:
        endpoints = _endpoints(settings.esewa_env)
        params = {
            "product_code": settings.esewa_product_code,
            "total_amount": int(round(payment.amount)),
            "transaction_uuid": payment.id,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(endpoints["status"], params=params)
                if resp.status_code == 200 and resp.json().get("status") == "COMPLETE":
                    return
                raise GatewayError("eSewa status check did not return COMPLETE")
        except GatewayError:
            raise
        except Exception as exc:  # network hiccup -> rely on the verified signature
            logger.warning("eSewa status check skipped: %s", exc)