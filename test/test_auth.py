from unittest.mock import patch

from .conftest import MOCK_PATIENT

SIGNUP_DATA = {
    "name": "New User",
    "email": "new@test.com",
    "password": "secret123",
    "role": "PATIENT",
}

LOGIN_DATA = {"email": "patient@test.com", "password": "secret123"}


class TestSignup:
    @patch("app.routers.auth.create_access_token", return_value="mock-token")
    def test_signup_success(self, mock_token, client, mock_db):
        mock_db.user.find_unique.return_value = None
        mock_db.user.create.return_value = MOCK_PATIENT

        response = client.post("/api/v1/auth/signup", json=SIGNUP_DATA)

        assert response.status_code == 201
        body = response.json()
        assert body["access_token"] == "mock-token"
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "patient@test.com"

    def test_signup_duplicate_email(self, client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT

        response = client.post("/api/v1/auth/signup", json=SIGNUP_DATA)

        assert response.status_code == 409
        assert "already registered" in response.text


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

    def test_change_password_wrong_current(self, patient_client):
        response = patient_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrongpass", "new_password": "newpass456"},
        )

        assert response.status_code == 400
        assert "incorrect" in response.text


class TestLogout:
    def test_logout(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 204


class TestAuthGuard:
    def test_get_me_requires_auth(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
