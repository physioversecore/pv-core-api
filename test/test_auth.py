from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from .conftest import MOCK_PATIENT, MOCK_THERAPIST_USER

SIGNUP_DATA = {
    "name": "New User",
    "email": "new@test.com",
    "password": "Secret123!",
    "role": "PATIENT",
}

LOGIN_DATA = {"email": "patient@test.com", "password": "secret123"}

NOW = datetime.now(timezone.utc)


class TestSendOtp:
    @patch(
        "app.routers.auth.create_otp",
        new_callable=AsyncMock,
        return_value={
            "created": True,
            "resend_after": 120,
            "to": "new@test.com",
            "name": "Test",
            "code": "123456",
            "purpose": "signup",
        },
    )
    @patch("app.routers.auth.send_otp_email", new_callable=AsyncMock)
    def test_send_otp_success(self, mock_email, mock_create, client, mock_db):
        mock_db.user.find_unique.return_value = None

        response = client.post("/api/v1/auth/send-otp", json={"email": "new@test.com", "name": "Test"})

        assert response.status_code == 200
        assert response.json()["message"] == "OTP sent successfully"
        assert response.json()["resend_after"] == 120
        mock_create.assert_awaited_once()
        mock_email.assert_awaited_once_with("new@test.com", "Test", "123456", "signup")

    def test_send_otp_duplicate_email(self, client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT

        response = client.post("/api/v1/auth/send-otp", json={"email": "patient@test.com", "name": "Test"})

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    @patch("app.routers.auth.create_otp", new_callable=AsyncMock)
    def test_send_otp_registered_email_gets_conflict(self, mock_create, client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT

        response = client.post("/api/v1/auth/send-otp", json={"email": "patient@test.com", "name": "Test"})

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]
        mock_create.assert_not_awaited()

    @patch(
        "app.routers.auth.create_otp",
        new_callable=AsyncMock,
        return_value={"created": False, "resend_after": 90},
    )
    def test_send_otp_cooldown(self, mock_create, client, mock_db):
        mock_db.user.find_unique.return_value = None

        response = client.post("/api/v1/auth/send-otp", json={"email": "new@test.com", "name": "Test"})

        assert response.status_code == 429
        assert "90" in response.json()["detail"]

    @patch(
        "app.routers.auth.create_otp",
        new_callable=AsyncMock,
        return_value={
            "created": True,
            "resend_after": 120,
            "to": "new@test.com",
            "name": "Test",
            "code": "654321",
            "purpose": "password_reset",
        },
    )
    @patch("app.routers.auth.send_otp_email", new_callable=AsyncMock)
    def test_forgot_password_schedules_background_email(self, mock_email, mock_create, client, mock_db):
        mock_db.user.find_unique.return_value = SimpleNamespace(
            id="user-1", email="new@test.com", name="Test"
        )

        response = client.post("/api/v1/auth/forgot-password", json={"email": "new@test.com"})

        assert response.status_code == 200
        mock_create.assert_awaited_once()
        mock_email.assert_awaited_once_with("new@test.com", "Test", "654321", "password_reset")


class TestVerifyOtp:
    @patch("app.routers.auth.verify_otp", new_callable=AsyncMock, return_value=True)
    def test_verify_otp_success(self, mock_verify, client, mock_db):
        response = client.post("/api/v1/auth/verify-otp", json={"email": "new@test.com", "code": "123456"})

        assert response.status_code == 200
        assert response.json()["verified"] is True

    @patch("app.routers.auth.verify_otp", new_callable=AsyncMock, return_value=False)
    def test_verify_otp_invalid_code(self, mock_verify, client, mock_db):
        response = client.post("/api/v1/auth/verify-otp", json={"email": "new@test.com", "code": "000000"})

        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]


class TestSignup:
    @patch("app.routers.auth.create_access_token", return_value="mock-token")
    def test_signup_success_after_otp(self, mock_token, client, mock_db):
        mock_db.user.find_unique.return_value = None
        mock_db.user.create.return_value = MOCK_PATIENT
        mock_db.emailverification.find_first.return_value = SimpleNamespace(
            id="otp-1", email="new@test.com", code="123456", purpose="signup",
            used=True, attempts=0, createdAt=NOW, expiresAt=NOW + timedelta(minutes=5),
        )

        response = client.post("/api/v1/auth/signup", json=SIGNUP_DATA)

        assert response.status_code == 201
        body = response.json()
        assert body["access_token"] == "mock-token"
        assert body["user"]["email"] == "patient@test.com"

    def test_signup_no_otp_verification(self, client, mock_db):
        mock_db.user.find_unique.return_value = None
        mock_db.emailverification.find_first.return_value = None

        response = client.post("/api/v1/auth/signup", json=SIGNUP_DATA)

        assert response.status_code == 400
        assert "not verified" in response.json()["detail"]

    def test_signup_duplicate_email(self, client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT

        response = client.post("/api/v1/auth/signup", json=SIGNUP_DATA)

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]


class TestTherapistSignupApproval:
    def _pending_therapist(self):
        return SimpleNamespace(
            id="therapist-new-1",
            name="New Therapist",
            email="newtherapist@test.com",
            password="x",
            role="THERAPIST",
            city="Kathmandu",
            phone="9800000003",
            specialty="Physiotherapy",
            status="PENDING",
            referralCode=None,
            createdAt=NOW,
            updatedAt=NOW,
        )

    @patch("app.routers.auth.create_therapist_signup", new_callable=AsyncMock)
    @patch("app.routers.auth.send_application_received_email", new_callable=AsyncMock, return_value=True)
    @patch("app.routers.auth.create_access_token")
    def test_therapist_signup_no_token_pending_and_email_sent(
        self, mock_token, mock_email, mock_cts, client, mock_db
    ):
        pending = self._pending_therapist()
        mock_db.user.find_unique.return_value = None
        mock_db.user.create.return_value = pending
        mock_db.emailverification.find_first.return_value = SimpleNamespace(
            id="otp-1", email="newtherapist@test.com", code="123456", purpose="signup",
            used=True, attempts=0, createdAt=NOW, expiresAt=NOW + timedelta(minutes=5),
        )

        response = client.post(
            "/api/v1/auth/signup",
            json={
                "name": "New Therapist",
                "email": "newtherapist@test.com",
                "password": "Secret123!",
                "role": "THERAPIST",
                "specialty": "Physiotherapy",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["access_token"] is None
        assert body["user"]["status"] == "PENDING"
        mock_cts.assert_awaited_once()
        mock_email.assert_awaited_once_with("newtherapist@test.com", "New Therapist")
        mock_token.assert_not_called()

    @patch("app.routers.auth.create_therapist_signup", new_callable=AsyncMock)
    @patch("app.routers.auth.send_application_received_email", new_callable=AsyncMock, return_value=True)
    @patch("app.routers.auth.create_access_token")
    def test_therapist_signup_without_password_sets_must_change(
        self, mock_token, mock_email, mock_cts, client, mock_db
    ):
        pending = self._pending_therapist()
        pending.mustChangePassword = True
        mock_db.user.find_unique.return_value = None
        mock_db.user.create.return_value = pending
        mock_db.emailverification.find_first.return_value = SimpleNamespace(
            id="otp-1", email="newtherapist@test.com", code="123456", purpose="signup",
            used=True, attempts=0, createdAt=NOW, expiresAt=NOW + timedelta(minutes=5),
        )

        response = client.post(
            "/api/v1/auth/signup",
            json={
                "name": "New Therapist",
                "email": "newtherapist@test.com",
                "role": "THERAPIST",
                "specialty": "Physiotherapy",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["access_token"] is None
        assert body["user"]["status"] == "PENDING"
        assert body["user"]["mustChangePassword"] is True
        mock_token.assert_not_called()

    @patch("app.routers.auth.generate_temp_password", return_value="placeholder123")
    def test_patient_signup_requires_password(self, mock_gen, client, mock_db):
        mock_db.user.find_unique.return_value = None
        mock_db.emailverification.find_first.return_value = SimpleNamespace(
            id="otp-1", email="patient@test.com", code="123456", purpose="signup",
            used=True, attempts=0, createdAt=NOW, expiresAt=NOW + timedelta(minutes=5),
        )

        response = client.post(
            "/api/v1/auth/signup",
            json={"name": "New Patient", "email": "new@test.com", "role": "PATIENT"},
        )

        assert response.status_code == 400
        assert "Password" in response.json()["detail"]


class TestLogin:
    @patch("app.routers.auth.authenticate_user", return_value=MOCK_PATIENT)
    @patch("app.routers.auth.create_access_token", return_value="mock-token")
    def test_login_success(self, mock_token, mock_auth, client):
        response = client.post("/api/v1/auth/login", json=LOGIN_DATA)

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "mock-token"
        assert body["user"]["id"] == "patient-1"

    @patch("app.routers.auth.authenticate_user", return_value=None)
    def test_login_invalid_credentials(self, mock_auth, client):
        response = client.post("/api/v1/auth/login", json=LOGIN_DATA)

        assert response.status_code == 401
        assert "Invalid" in response.text


class TestLoginTherapistApprovalGate:
    def _therapist(self, status):
        return SimpleNamespace(
            id="therapist-user-1",
            name="Test Therapist",
            email="therapist@test.com",
            password="x",
            role="THERAPIST",
            status=status,
        )

    @patch("app.routers.auth.authenticate_user")
    def test_login_pending_therapist_blocked(self, mock_auth, client):
        mock_auth.return_value = self._therapist("PENDING")

        response = client.post("/api/v1/auth/login", json=LOGIN_DATA)

        assert response.status_code == 403
        assert "under review" in response.json()["detail"]

    @patch("app.routers.auth.authenticate_user")
    def test_login_rejected_therapist_blocked(self, mock_auth, client):
        mock_auth.return_value = self._therapist("REJECTED")

        response = client.post("/api/v1/auth/login", json=LOGIN_DATA)

        assert response.status_code == 403
        assert "not approved" in response.json()["detail"]

    @patch("app.routers.auth.authenticate_user")
    @patch("app.routers.auth.create_access_token", return_value="mock-token")
    def test_login_approved_therapist_allowed(self, mock_token, mock_auth, client):
        mock_auth.return_value = self._therapist("APPROVED")

        response = client.post("/api/v1/auth/login", json=LOGIN_DATA)

        assert response.status_code == 200
        assert response.json()["access_token"] == "mock-token"
        assert response.json()["user"]["mustChangePassword"] is False

    @patch("app.routers.auth.create_access_token", return_value="mock-token")
    @patch("app.routers.auth.authenticate_user")
    def test_login_temp_password_user_flagged(self, mock_auth, mock_token, client):
        therapist = self._therapist("APPROVED")
        therapist.mustChangePassword = True
        mock_auth.return_value = therapist

        response = client.post("/api/v1/auth/login", json=LOGIN_DATA)

        assert response.status_code == 200
        assert response.json()["user"]["mustChangePassword"] is True


class TestMe:
    def test_get_me(self, patient_client):
        response = patient_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        assert response.json()["id"] == "patient-1"
        assert response.json()["email"] == "patient@test.com"

    def test_update_me(self, patient_client, mock_db):
        mock_db.user.update.return_value = MOCK_PATIENT

        response = patient_client.put(
            "/api/v1/auth/me", json={"name": "Updated Name"}
        )

        assert response.status_code == 200
        assert response.json()["email"] == "patient@test.com"


class TestChangePassword:
    @patch("app.routers.auth.verify_password", return_value=True)
    def test_change_password_success(self, mock_verify, patient_client, mock_db):
        mock_db.user.update.return_value = MOCK_PATIENT

        response = patient_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "secret123", "new_password": "newpass456"},
        )

        assert response.status_code == 204
        mock_db.user.update.assert_awaited_once()
        update_data = mock_db.user.update.await_args.kwargs["data"]
        assert update_data["mustChangePassword"] is False

    def test_change_password_wrong_current(self, patient_client):
        response = patient_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrongpass", "new_password": "newpass456"},
        )

        assert response.status_code == 400
        assert "incorrect" in response.text


class TestDeleteAccount:
    @patch("app.routers.auth.verify_password", return_value=True)
    def test_delete_account_success(self, mock_verify, patient_client, mock_db):
        mock_db.user.delete.return_value = MOCK_PATIENT

        response = patient_client.post("/api/v1/auth/delete-account", json={"password": "secret123"})

        assert response.status_code == 204
        mock_db.user.delete.assert_awaited_once_with(where={"id": MOCK_PATIENT.id})

    def test_delete_account_without_password(self, patient_client, mock_db):
        mock_db.user.delete.return_value = MOCK_PATIENT

        response = patient_client.post("/api/v1/auth/delete-account", json={})

        assert response.status_code == 204
        mock_db.user.delete.assert_awaited_once_with(where={"id": MOCK_PATIENT.id})

    @patch("app.routers.auth.verify_password", return_value=False)
    def test_delete_account_wrong_password(self, mock_verify, patient_client):
        response = patient_client.post(
            "/api/v1/auth/delete-account", json={"password": "wrongpass"}
        )

        assert response.status_code == 400
        assert "incorrect" in response.text

    def test_delete_account_requires_auth(self, client):
        response = client.post("/api/v1/auth/delete-account", json={"password": "x"})
        assert response.status_code in (401, 403)


class TestLogout:
    def test_logout(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 204


class TestAuthGuard:
    def test_get_me_requires_auth(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
