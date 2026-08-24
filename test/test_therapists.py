from unittest.mock import patch

from .conftest import MOCK_THERAPIST_PROFILE, MOCK_THERAPIST_USER, MOCK_PATIENT

THERAPIST_CREATE_DATA = {
    "name": "Dr. Therapist",
    "specialty": "Physiotherapy",
    "city": "Kathmandu",
    "gender": "Male",
    "price": 1500.0,
    "experience": 5,
    "bio": "Experienced physiotherapist",
}


class TestListTherapists:
    def test_list_therapists(self, client, mock_db):
        mock_db.therapist.find_many.return_value = [MOCK_THERAPIST_PROFILE]
        mock_db.therapist.count.return_value = 1

        response = client.get("/api/v1/therapists")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["therapists"]) == 1
        assert body["therapists"][0]["id"] == "therapist-1"

    def test_list_therapists_pagination(self, client, mock_db):
        mock_db.therapist.find_many.return_value = []
        mock_db.therapist.count.return_value = 0

        response = client.get("/api/v1/therapists?skip=0&limit=10")

        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_therapists_search_matches_multiple_fields(self, client, mock_db):
        mock_db.therapist.find_many.return_value = []
        mock_db.therapist.count.return_value = 0

        response = client.get("/api/v1/therapists?search=Kathmandu")

        assert response.status_code == 200
        _, kwargs = mock_db.therapist.find_many.call_args
        assert kwargs["where"]["OR"] == [
            {"name": {"contains": "Kathmandu", "mode": "insensitive"}},
            {"specialty": {"contains": "Kathmandu", "mode": "insensitive"}},
            {"city": {"contains": "Kathmandu", "mode": "insensitive"}},
            {"gender": {"contains": "Kathmandu", "mode": "insensitive"}},
        ]

    def test_list_therapists_search_combines_with_exact_filters(self, client, mock_db):
        mock_db.therapist.find_many.return_value = []
        mock_db.therapist.count.return_value = 0

        response = client.get("/api/v1/therapists?search=Male&specialty=Physiotherapy")

        assert response.status_code == 200
        _, kwargs = mock_db.therapist.find_many.call_args
        assert kwargs["where"]["OR"] is not None
        assert kwargs["where"]["specialty"] == "Physiotherapy"


class TestGetMyProfile:
    def test_get_my_profile_success(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        response = therapist_client.get("/api/v1/therapists/me")

        assert response.status_code == 200
        assert response.json()["id"] == "therapist-1"

    def test_get_my_profile_forbidden_for_patient(self, patient_client):
        response = patient_client.get("/api/v1/therapists/me")

        assert response.status_code == 403

    def test_get_my_profile_not_found(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = None

        response = therapist_client.get("/api/v1/therapists/me")

        assert response.status_code == 404


class TestGetTherapistById:
    def test_get_by_id_success(self, client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.user.find_unique.return_value = MOCK_THERAPIST_USER

        response = client.get("/api/v1/therapists/therapist-1")

        assert response.status_code == 200
        assert response.json()["id"] == "therapist-1"

    def test_get_by_id_hidden_when_unapproved(self, client, mock_db):
        from types import SimpleNamespace

        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.user.find_unique.return_value = SimpleNamespace(
            id="therapist-user-1", status="PENDING"
        )

        response = client.get("/api/v1/therapists/therapist-1")

        assert response.status_code == 404

    def test_get_by_id_not_found(self, client, mock_db):
        mock_db.therapist.find_unique.return_value = None

        response = client.get("/api/v1/therapists/unknown")

        assert response.status_code == 404


class TestCreateTherapist:
    def test_create_success(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = None
        mock_db.therapist.create.return_value = MOCK_THERAPIST_PROFILE

        response = therapist_client.post(
            "/api/v1/therapists", json=THERAPIST_CREATE_DATA
        )

        assert response.status_code == 201
        assert response.json()["id"] == "therapist-1"

    def test_create_forbidden_for_patient(self, patient_client):
        response = patient_client.post(
            "/api/v1/therapists", json=THERAPIST_CREATE_DATA
        )

        assert response.status_code == 403

    def test_create_conflict(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        response = therapist_client.post(
            "/api/v1/therapists", json=THERAPIST_CREATE_DATA
        )

        assert response.status_code == 409


class TestUpdateTherapist:
    def test_update_by_owner(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.therapist.update.return_value = MOCK_THERAPIST_PROFILE

        response = therapist_client.put(
            "/api/v1/therapists/therapist-1", json={"name": "Updated"}
        )

        assert response.status_code == 200

    def test_update_by_admin(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.therapist.update.return_value = MOCK_THERAPIST_PROFILE

        response = admin_client.put(
            "/api/v1/therapists/therapist-1", json={"name": "Updated"}
        )

        assert response.status_code == 200

    def test_update_by_non_owner_forbidden(self, patient_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        response = patient_client.put(
            "/api/v1/therapists/therapist-1", json={"name": "Updated"}
        )

        assert response.status_code == 403

    def test_update_not_found(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = None

        response = therapist_client.put(
            "/api/v1/therapists/unknown", json={"name": "Updated"}
        )

        assert response.status_code == 404


class TestDeleteTherapist:
    def test_delete_by_owner(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        response = therapist_client.delete("/api/v1/therapists/therapist-1")

        assert response.status_code == 204

    def test_delete_by_admin(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        response = admin_client.delete("/api/v1/therapists/therapist-1")

        assert response.status_code == 204

    def test_delete_by_non_owner_forbidden(self, patient_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        response = patient_client.delete("/api/v1/therapists/therapist-1")

        assert response.status_code == 403

    def test_delete_not_found(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = None

        response = therapist_client.delete("/api/v1/therapists/unknown")

        assert response.status_code == 404
