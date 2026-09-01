from .conftest import MOCK_PAYMENT

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


class TestProcessBooking:
    def test_process_conflict_returns_409(self, patient_client, mock_db):
        mock_db.familymember.find_unique.return_value = None
        mock_db.session.find_many.return_value = [MOCK_PAYMENT]

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
