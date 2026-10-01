import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_PAYMENT, MOCK_SESSION

PAYMENT_CREATE_DATA = {
    "amount": 1000.0,
    "method": "CASH",
}

BOOKING_PROCESS_DATA = {
    "therapistId": "therapist-1",
    "date": "2024-07-01T10:00:00",
    "time": "10:00",
    "type": "HOME_VISIT",
    "address": "Test Address",
    "fee": 1500.0,
    "currency": "NPR",
    "paymentMethod": "CASH",
    "platformFee": 75.0,
}

ESEWA_BOOKING_DATA = {
    **BOOKING_PROCESS_DATA,
    "paymentMethod": "esewa",
}


class TestProcessBooking:
    def test_process_conflict_returns_409(self, patient_client, mock_db):
        mock_db.familymember.find_unique.return_value = None
        mock_db.session.count.return_value = 1

        response = patient_client.post(
            "/api/v1/payments/process", json=BOOKING_PROCESS_DATA
        )

        assert response.status_code == 409
        assert "booked" in response.json()["detail"].lower()
        mock_db.session.create.assert_not_awaited()


class TestCreatePayment:
    def test_create_payment(self, patient_client, mock_db):
        mock_db.payment.create.return_value = MOCK_PAYMENT

        response = patient_client.post("/api/v1/payments", json=PAYMENT_CREATE_DATA)

        assert response.status_code == 201
        assert response.json()["id"] == "payment-1"
        assert response.json()["amount"] == 1000.0


class TestListPayments:
    def test_list_as_patient(self, patient_client, mock_db):
        mock_db.payment.find_many.return_value = [MOCK_PAYMENT]
        mock_db.payment.count.return_value = 1

        response = patient_client.get("/api/v1/payments")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["payments"][0]["id"] == "payment-1"

    def test_list_as_admin(self, admin_client, mock_db):
        mock_db.payment.find_many.return_value = [MOCK_PAYMENT]
        mock_db.payment.count.return_value = 1

        response = admin_client.get("/api/v1/payments")

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_empty(self, patient_client, mock_db):
        mock_db.payment.find_many.return_value = []
        mock_db.payment.count.return_value = 0

        response = patient_client.get("/api/v1/payments")

        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestGetPayment:
    def test_get_by_id(self, patient_client, mock_db):
        mock_db.payment.find_unique.return_value = MOCK_PAYMENT

        response = patient_client.get("/api/v1/payments/payment-1")

        assert response.status_code == 200
        assert response.json()["id"] == "payment-1"

    def test_get_not_found(self, patient_client, mock_db):
        mock_db.payment.find_unique.return_value = None

        response = patient_client.get("/api/v1/payments/unknown")

        assert response.status_code == 404


class TestUpdatePaymentStatus:
    def test_update_status_by_admin(self, admin_client, mock_db):
        mock_db.payment.find_unique.return_value = MOCK_PAYMENT
        mock_db.payment.update.return_value = MOCK_PAYMENT

        response = admin_client.put(
            "/api/v1/payments/payment-1/status?new_status=COMPLETED"
        )

        assert response.status_code == 200
        assert response.json()["id"] == "payment-1"

    def test_update_status_by_non_admin_forbidden(self, patient_client):
        response = patient_client.put(
            "/api/v1/payments/payment-1/status?new_status=COMPLETED"
        )

        assert response.status_code == 403

    def test_update_status_not_found(self, admin_client, mock_db):
        mock_db.payment.find_unique.return_value = None

        response = admin_client.put(
            "/api/v1/payments/unknown/status?new_status=COMPLETED"
        )

        assert response.status_code == 404


# ─── eSewa signature (pure, no DB/network) ──────────────────────────────────


class TestEsewaSignature:
    def test_sign_and_verify(self):
        from app.services.payments.esewa import _sign, _verify_response_signature
        from app import settings

        amount, txn_uuid, product_code, secret = (
            1000,
            "txn-abc-123",
            settings.esewa_product_code or "EPAYTEST",
            settings.esewa_secret_key or "8gBm/:&EnhH.1/q",
        )

        sig = _sign(amount, txn_uuid, product_code, secret)
        assert isinstance(sig, str) and len(sig) > 10

        # A valid response should have signed_field_names + matching signature.
        fields = "total_amount,transaction_uuid,product_code,status,signed_field_names"
        data = {
            "total_amount": str(amount),
            "transaction_uuid": txn_uuid,
            "product_code": product_code,
            "status": "COMPLETE",
            "signed_field_names": fields,
        }
        # Re-compute the signature using the canonical callback ordering.
        import base64, hashlib, hmac

        message = ",".join(f"{f}={data.get(f, '')}" for f in fields.split(","))
        data["signature"] = base64.b64encode(
            hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()
        assert _verify_response_signature(data, secret)

    def test_verify_rejects_bad_signature(self):
        from app.services.payments.esewa import _verify_response_signature

        data = {
            "total_amount": "1000",
            "transaction_uuid": "x",
            "product_code": "EPAYTEST",
            "status": "COMPLETE",
            "signed_field_names": "total_amount,transaction_uuid,product_code,status,signed_field_names",
            "signature": "AAAA",
        }
        assert not _verify_response_signature(data, "wrong-secret")


# ─── process_booking with eSewa returns PENDING + initiation ────────────────


class TestProcessBookingEsewa:
    @patch("app.services.payments.esewa.httpx")
    def test_process_esewa_returns_pending_initiation(
        self, mock_httpx, patient_client, mock_db, monkeypatch
    ):
        from app import settings
        from app.routers import payments as payments_router

        monkeypatch.setattr(settings, "esewa_secret_key", "8gBm/:&EnhH.1/q")
        monkeypatch.setattr(settings, "esewa_product_code", "EPAYTEST")
        monkeypatch.setattr(settings, "esewa_env", "uat")
        monkeypatch.setattr(settings, "esewa_success_url", "http://localhost:3000/api/webhooks/payments/esewa")
        monkeypatch.setattr(settings, "esewa_failure_url", "http://localhost:3000/api/webhooks/payments/esewa?status=failed")

        # Stub create_session to return an enrichment-shaped dict (as the real
        # service does).
        enriched_session = {
            "id": "session-1",
            "therapistId": "therapist-1",
            "therapistName": "Dr. Therapist",
            "patientId": "patient-1",
            "patientPhone": "9800000001",
            "familyMemberId": None,
            "familyMemberName": None,
            "date": MOCK_SESSION.date,
            "time": "10:00",
            "type": "HOME_VISIT",
            "status": "SCHEDULED",
            "address": "Test Address",
            "fee": 1500.0,
            "notes": None,
            "createdAt": MOCK_SESSION.createdAt,
            "updatedAt": MOCK_SESSION.updatedAt,
        }
        mock_create_session = AsyncMock(return_value=enriched_session)
        monkeypatch.setattr(payments_router, "create_session", mock_create_session)

        payment_obj = SimpleNamespace(
            id="pymt-esewa-1",
            userId="patient-1",
            amount=1575.0,
            status="PENDING",
            method="ESEWA",
            sessionId="session-1",
            currency="NPR",
            platformFee=75.0,
            paymentType="nepal",
            transactionRef=None,
            cardLast4=None,
            walletMobile=None,
            billingCountry=None,
            createdAt=MOCK_PAYMENT.createdAt,
            updatedAt=MOCK_PAYMENT.updatedAt,
        )
        mock_db.payment.create.return_value = payment_obj
        # Gateway.initiate may call payment.update to store refs; mock that.
        mock_db.payment.update.return_value = payment_obj
        # Router re-reads the payment after initiate to reflect stored refs.
        mock_db.payment.find_unique.return_value = payment_obj

        response = patient_client.post(
            "/api/v1/payments/process", json=ESEWA_BOOKING_DATA
        )

        assert response.status_code == 201
        body = response.json()
        assert body["payment"]["status"] == "PENDING"
        init = body.get("initiation")
        assert init is not None
        assert init["type"] == "form"
        assert "esewa" in (init["url"] or "").lower()
        assert init["formFields"] is not None


# ─── confirm endpoint ────────────────────────────────────────────────────────


class TestGatewaySelection:
    def test_gateway_methods(self):
        from app.services.payments import GATEWAY_METHODS, is_gateway_method

        assert "esewa" in GATEWAY_METHODS
        assert "khalti" in GATEWAY_METHODS
        assert is_gateway_method("esewa")
        assert is_gateway_method("khalti")
        assert is_gateway_method("ESEWA")
        # Not implemented yet — must stay on the manual/legacy path.
        assert not is_gateway_method("connectips")
        assert not is_gateway_method("cash")
        assert not is_gateway_method("fonepay")

    def test_imepay_aliases_to_khalti(self):
        from app.services.payments import is_gateway_method, normalize_method

        assert normalize_method("imepay") == "khalti"
        assert normalize_method("ImePay") == "khalti"
        assert is_gateway_method("imepay")

    def test_connectips_falls_back_to_manual_gateway(self):
        from app.services.payments import get_gateway

        gw = get_gateway("connectips")
        assert gw.name == "manual"


class TestConfirmPayment:
    def test_confirm_cash_already_completed(self, patient_client, mock_db):
        """Cash payments are immediately COMPLETED; confirm is idempotent."""
        cash_payment = SimpleNamespace(
            id="pymt-cash-1",
            userId="patient-1",
            amount=1500.0,
            status="COMPLETED",
            method="CASH",
            sessionId=None,
            currency="NPR",
            platformFee=75.0,
            paymentType=None,
            transactionRef=None,
            cardLast4=None,
            walletMobile=None,
            billingCountry=None,
            createdAt=MOCK_PAYMENT.createdAt,
            updatedAt=MOCK_PAYMENT.updatedAt,
        )
        mock_db.payment.find_unique.return_value = cash_payment
        mock_db.payment.update.return_value = cash_payment

        response = patient_client.post(
            "/api/v1/payments/pymt-cash-1/confirm",
            json={"params": {}},
        )

        assert response.status_code == 200
        assert response.json()["result"] == "already_completed"

    def test_confirm_gateway_not_found(self, patient_client, mock_db):
        mock_db.payment.find_unique.return_value = None
        response = patient_client.post(
            "/api/v1/payments/unknown/confirm",
            json={"params": {}},
        )
        assert response.status_code == 404

    def test_confirm_wrong_owner(self, patient_client, mock_db):
        other_payment = SimpleNamespace(id="pymt-other", userId="someone-else", status="PENDING", method="ESEWA")
        mock_db.payment.find_unique.return_value = other_payment

        response = patient_client.post(
            "/api/v1/payments/pymt-other/confirm",
            json={"params": {}},
        )
        assert response.status_code == 404
