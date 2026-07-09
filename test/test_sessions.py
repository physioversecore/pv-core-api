from datetime import datetime

from .conftest import MOCK_SESSION, MOCK_THERAPIST_PROFILE

SESSION_CREATE_DATA = {
    "therapistId": "therapist-1",
    "date": "2024-07-01T10:00:00",
    "time": "10:00",
    "type": "HOME_VISIT",
    "address": "Test Address",
    "fee": 1500.0,
    "notes": None,
}


class TestCreateSession:
    def test_create_by_patient(self, patient_client, mock_db):
        mock_db.session.create.return_value = MOCK_SESSION

        response = patient_client.post("/api/v1/sessions", json=SESSION_CREATE_DATA)

        assert response.status_code == 201
        assert response.json()["id"] == "session-1"

    def test_create_by_therapist_forbidden(self, therapist_client):
        response = therapist_client.post(
            "/api/v1/sessions", json=SESSION_CREATE_DATA
        )

        assert response.status_code == 403


class TestListSessions:
    def test_list_as_patient(self, patient_client, mock_db):
        mock_db.session.find_many.return_value = [MOCK_SESSION]
        mock_db.session.count.return_value = 1

        response = patient_client.get("/api/v1/sessions")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sessions"][0]["id"] == "session-1"

    def test_list_as_therapist(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.session.find_many.return_value = [MOCK_SESSION]
        mock_db.session.count.return_value = 1

        response = therapist_client.get("/api/v1/sessions")

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_as_therapist_no_profile(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = None

        response = therapist_client.get("/api/v1/sessions")

        assert response.status_code == 404

    def test_list_as_admin(self, admin_client, mock_db):
        mock_db.session.find_many.return_value = [MOCK_SESSION]
        mock_db.session.count.return_value = 1

        response = admin_client.get("/api/v1/sessions")

        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestGetSession:
    def test_get_by_id(self, patient_client, mock_db):
        mock_db.session.find_unique.return_value = MOCK_SESSION

        response = patient_client.get("/api/v1/sessions/session-1")

        assert response.status_code == 200
        assert response.json()["id"] == "session-1"

    def test_get_not_found(self, patient_client, mock_db):
        mock_db.session.find_unique.return_value = None

        response = patient_client.get("/api/v1/sessions/unknown")

        assert response.status_code == 404


class TestUpdateSession:
    def test_update_by_patient(self, patient_client, mock_db):
        mock_db.session.find_unique.return_value = MOCK_SESSION
        mock_db.session.update.return_value = MOCK_SESSION

        response = patient_client.put(
            "/api/v1/sessions/session-1", json={"status": "CANCELLED"}
        )

        assert response.status_code == 200

    def test_update_by_admin(self, admin_client, mock_db):
        mock_db.session.find_unique.return_value = MOCK_SESSION
        mock_db.session.update.return_value = MOCK_SESSION

        response = admin_client.put(
            "/api/v1/sessions/session-1", json={"status": "CANCELLED"}
        )

        assert response.status_code == 200

    def test_update_by_non_owner_forbidden(self, therapist_client, mock_db):
        mock_db.session.find_unique.return_value = MOCK_SESSION

        response = therapist_client.put(
            "/api/v1/sessions/session-1", json={"status": "CANCELLED"}
        )

        assert response.status_code == 403

    def test_update_not_found(self, patient_client, mock_db):
        mock_db.session.find_unique.return_value = None

        response = patient_client.put(
            "/api/v1/sessions/unknown", json={"status": "CANCELLED"}
        )

        assert response.status_code == 404


class TestDeleteSession:
    def test_delete_by_patient(self, patient_client, mock_db):
        mock_db.session.find_unique.return_value = MOCK_SESSION

        response = patient_client.delete("/api/v1/sessions/session-1")

        assert response.status_code == 204

    def test_delete_by_admin(self, admin_client, mock_db):
        mock_db.session.find_unique.return_value = MOCK_SESSION

        response = admin_client.delete("/api/v1/sessions/session-1")

        assert response.status_code == 204

    def test_delete_by_non_owner_forbidden(self, therapist_client, mock_db):
        mock_db.session.find_unique.return_value = MOCK_SESSION

        response = therapist_client.delete("/api/v1/sessions/session-1")

        assert response.status_code == 403

    def test_delete_not_found(self, patient_client, mock_db):
        mock_db.session.find_unique.return_value = None

        response = patient_client.delete("/api/v1/sessions/unknown")

        assert response.status_code == 404
