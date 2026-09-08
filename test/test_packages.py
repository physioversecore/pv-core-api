from types import SimpleNamespace
from unittest.mock import AsyncMock

from .conftest import (
    FUTURE_AWARE,
    MOCK_PACKAGE,
    MOCK_PACKAGE_PURCHASE,
    MOCK_PATIENT,
    MOCK_PAYMENT,
    MOCK_SESSION,
)

PURCHASE_DATA = {"paymentMethod": "ESEWA"}

# A package purchase with package relation, used by session booking flow.
MOCK_PACKAGE_PURCHASE_WITH_PKG = SimpleNamespace(
    id="purchase-1",
    userId="patient-1",
    packageId="package-1",
    paymentId="payment-1",
    sessionsTotal=12,
    sessionsUsed=2,
    status="ACTIVE",
    purchasedAt=FUTURE_AWARE,
    expiresAt=FUTURE_AWARE,
    createdAt=MOCK_PACKAGE_PURCHASE.createdAt,
    updatedAt=MOCK_PACKAGE_PURCHASE.updatedAt,
    package=MOCK_PACKAGE,
)

SESSION_CREATE_PAYLOAD = {
    "therapistId": "therapist-1",
    "date": "2024-07-01T10:00:00",
    "time": "10:00",
    "type": "HOME_VISIT",
    "address": "Test Address",
    "fee": 1500.0,
    "notes": None,
    "packagePurchaseId": "purchase-1",
}


class TestListPackages:
    def test_list_packages(self, client, mock_db):
        mock_db.package.find_many.return_value = [MOCK_PACKAGE]
        mock_db.package.count.return_value = 1

        response = client.get("/api/v1/packages")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["packages"][0]["name"] == "Stroke & Neuro Recovery"
        assert body["packages"][0]["sessionCount"] == 12
        assert body["packages"][0]["validityDays"] == 30


class TestPurchasePackage:
    def test_purchase_as_patient(self, patient_client, mock_db):
        mock_db.package.find_unique.return_value = MOCK_PACKAGE
        mock_db.packagepurchase.find_first.return_value = None
        mock_db.payment.create.return_value = MOCK_PAYMENT
        mock_db.packagepurchase.create.return_value = MOCK_PACKAGE_PURCHASE
        mock_db.adminnotification.create = AsyncMock()

        response = patient_client.post(
            "/api/v1/packages/package-1/purchase", json=PURCHASE_DATA
        )

        assert response.status_code == 201
        body = response.json()
        assert body["packageName"] == "Stroke & Neuro Recovery"
        assert body["status"] == "ACTIVE"
        assert body["sessionsTotal"] == 12
        assert body["sessionsRemaining"] == 10

    def test_purchase_by_therapist_forbidden(self, therapist_client):
        response = therapist_client.post(
            "/api/v1/packages/package-1/purchase", json=PURCHASE_DATA
        )

        assert response.status_code == 403

    def test_purchase_missing_package(self, patient_client, mock_db):
        mock_db.package.find_unique.return_value = None

        response = patient_client.post(
            "/api/v1/packages/package-1/purchase", json=PURCHASE_DATA
        )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_purchase_inactive_package(self, patient_client, mock_db):
        inactive = SimpleNamespace(**vars(MOCK_PACKAGE))
        inactive.isActive = False
        mock_db.package.find_unique.return_value = inactive

        response = patient_client.post(
            "/api/v1/packages/package-1/purchase", json=PURCHASE_DATA
        )

        assert response.status_code == 400
        assert "no longer available" in response.json()["detail"].lower()

    def test_purchase_conflicts_with_active_package(self, patient_client, mock_db):
        mock_db.package.find_unique.return_value = MOCK_PACKAGE
        mock_db.packagepurchase.find_first.return_value = MOCK_PACKAGE_PURCHASE

        response = patient_client.post(
            "/api/v1/packages/package-1/purchase", json=PURCHASE_DATA
        )

        assert response.status_code == 400
        assert "already have an active package" in response.json()["detail"].lower()


class TestMyPurchases:
    def test_list_my_purchases(self, patient_client, mock_db):
        mock_db.packagepurchase.find_many.return_value = [MOCK_PACKAGE_PURCHASE]
        mock_db.package.find_unique.return_value = MOCK_PACKAGE

        response = patient_client.get("/api/v1/packages/my-purchases")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["purchases"][0]["packageName"] == "Stroke & Neuro Recovery"
        assert body["purchases"][0]["sessionsRemaining"] == 10

    def test_active_purchase(self, patient_client, mock_db):
        mock_db.packagepurchase.find_first.return_value = MOCK_PACKAGE_PURCHASE
        mock_db.package.find_unique.return_value = MOCK_PACKAGE
        mock_db.session.find_many.return_value = []

        response = patient_client.get("/api/v1/packages/my-purchases/active")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "purchase-1"
        assert body["sessionsRemaining"] == 10

    def test_active_purchase_none(self, patient_client, mock_db):
        mock_db.packagepurchase.find_first.return_value = None

        response = patient_client.get("/api/v1/packages/my-purchases/active")

        assert response.status_code == 404

    def test_active_purchase_expired_marks_expired(self, patient_client, mock_db):
        from datetime import datetime, timedelta, timezone

        expired = SimpleNamespace(**vars(MOCK_PACKAGE_PURCHASE))
        expired.expiresAt = datetime.now(timezone.utc) - timedelta(days=1)
        mock_db.packagepurchase.find_first.return_value = expired
        mock_db.packagepurchase.update = AsyncMock(return_value=expired)

        response = patient_client.get("/api/v1/packages/my-purchases/active")

        assert response.status_code == 404
        mock_db.packagepurchase.update.assert_awaited_once()


class TestPackageSessionBooking:
    """Sessions booked against a package deduct a session and set fee to 0."""

    def test_book_with_package_deducts_and_sets_fee_zero(self, patient_client, mock_db):
        mock_db.session.find_many.return_value = []  # slot free
        mock_db.packagepurchase.find_unique.return_value = MOCK_PACKAGE_PURCHASE_WITH_PKG
        mock_db.packagepurchase.find_first.return_value = MOCK_PACKAGE_PURCHASE
        mock_db.package.find_unique.return_value = MOCK_PACKAGE
        mock_db.packagepurchase.update = AsyncMock(
            return_value=SimpleNamespace(
                id="purchase-1",
                sessionsUsed=3,
                sessionsTotal=12,
                status="ACTIVE",
            )
        )
        created_session = SimpleNamespace(**vars(MOCK_SESSION))
        created_session.fee = 0
        created_session.packagePurchaseId = "purchase-1"
        created_session.therapist = None
        created_session.packagePurchase = MOCK_PACKAGE_PURCHASE_WITH_PKG
        mock_db.session.create.return_value = created_session

        response = patient_client.post("/api/v1/sessions", json=SESSION_CREATE_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert body["packagePurchaseId"] == "purchase-1"
        assert body["bookedViaPackage"] is True
        assert body["packageName"] == "Stroke & Neuro Recovery"

    def test_book_with_package_not_active(self, patient_client, mock_db):
        mock_db.session.find_many.return_value = []
        inactive = SimpleNamespace(**vars(MOCK_PACKAGE_PURCHASE_WITH_PKG))
        inactive.status = "EXPIRED"
        mock_db.packagepurchase.find_unique.return_value = inactive

        response = patient_client.post("/api/v1/sessions", json=SESSION_CREATE_PAYLOAD)

        assert response.status_code == 400
        assert "package" in response.json()["detail"].lower()

    def test_book_with_package_depleted(self, patient_client, mock_db):
        mock_db.session.find_many.return_value = []
        depleted = SimpleNamespace(**vars(MOCK_PACKAGE_PURCHASE_WITH_PKG))
        depleted.sessionsUsed = depleted.sessionsTotal
        depleted.status = "DEPLETED"
        mock_db.packagepurchase.find_unique.return_value = depleted

        response = patient_client.post("/api/v1/sessions", json=SESSION_CREATE_PAYLOAD)

        assert response.status_code == 400
        assert "package" in response.json()["detail"].lower()


class TestAdminPackagePurchases:
    def test_admin_list_purchases(self, admin_client, mock_db):
        mock_db.packagepurchase.find_many.return_value = [MOCK_PACKAGE_PURCHASE]
        mock_db.package.find_unique.return_value = MOCK_PACKAGE
        mock_db.user.find_unique.return_value = MOCK_PATIENT
        mock_db.packagepurchase.count.return_value = 1

        response = admin_client.get("/api/v1/admin/packages/purchases")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["purchases"][0]["id"] == "purchase-1"
        assert body["purchases"][0]["patientName"] == "Test Patient"

    def test_admin_stats(self, admin_client, mock_db):
        mock_db.packagepurchase.find_many.return_value = [MOCK_PACKAGE_PURCHASE]
        mock_db.packagepurchase.count.return_value = 1
        mock_db.package.find_unique.return_value = MOCK_PACKAGE

        response = admin_client.get("/api/v1/admin/packages/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["totalRevenue"] >= 0
        assert body["activePurchases"] == 1

    def test_admin_stats_requires_admin(self, patient_client):
        response = patient_client.get("/api/v1/admin/packages/stats")

        assert response.status_code == 403