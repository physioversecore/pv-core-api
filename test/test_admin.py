from .conftest import MOCK_PATIENT, MOCK_THERAPIST_USER, MOCK_ADMIN


class TestListUsers:
    def test_list_users(self, admin_client, mock_db):
        mock_db.user.find_many.return_value = [MOCK_PATIENT, MOCK_THERAPIST_USER]

        response = admin_client.get("/api/v1/admin/users")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["id"] == "patient-1"

    def test_list_users_filter_by_role(self, admin_client, mock_db):
        mock_db.user.find_many.return_value = [MOCK_THERAPIST_USER]

        response = admin_client.get("/api/v1/admin/users?role=THERAPIST")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["role"] == "THERAPIST"

    def test_list_users_forbidden_for_non_admin(self, patient_client):
        response = patient_client.get("/api/v1/admin/users")
        assert response.status_code == 403


class TestUpdateUserStatus:
    def test_update_status(self, admin_client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT
        mock_db.user.update.return_value = MOCK_PATIENT

        response = admin_client.put(
            "/api/v1/admin/users/patient-1/status?new_status=APPROVED"
        )

        assert response.status_code == 200
        assert response.json()["id"] == "patient-1"

    def test_update_status_forbidden_for_non_admin(self, patient_client):
        response = patient_client.put(
            "/api/v1/admin/users/patient-1/status?new_status=APPROVED"
        )

        assert response.status_code == 403

    def test_update_status_not_found(self, admin_client, mock_db):
        mock_db.user.find_unique.return_value = None

        response = admin_client.put(
            "/api/v1/admin/users/unknown/status?new_status=APPROVED"
        )

        assert response.status_code == 404


class TestListPendingTherapists:
    def test_list_pending_therapists(self, admin_client, mock_db):
        mock_db.user.find_many.return_value = [MOCK_THERAPIST_USER]

        response = admin_client.get("/api/v1/admin/therapists/pending")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["role"] == "THERAPIST"

    def test_list_pending_empty(self, admin_client, mock_db):
        mock_db.user.find_many.return_value = []

        response = admin_client.get("/api/v1/admin/therapists/pending")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_pending_forbidden_for_non_admin(self, patient_client):
        response = patient_client.get("/api/v1/admin/therapists/pending")
        assert response.status_code == 403
