from datetime import datetime
from types import SimpleNamespace

from .conftest import MOCK_PATIENT, MOCK_THERAPIST_USER, MOCK_ADMIN

NOW = datetime(2024, 6, 15, 10, 30, 0)

MOCK_THERAPIST_USER_WITH_PROFILE = SimpleNamespace(
    id="therapist-user-1",
    name="Test Therapist",
    email="therapist@test.com",
    password="$2b$12$LJ3m4ys3Lk0TSwHlOR./YuVF4vj4G.hC3sVJfFJkVixRClvD1zBWe",
    role="THERAPIST",
    city="Kathmandu",
    phone="9800000002",
    specialty="Physiotherapy",
    status="APPROVED",
    referralCode=None,
    createdAt=NOW,
    updatedAt=NOW,
    therapist=SimpleNamespace(
        id="therapist-1",
        userId="therapist-user-1",
        name="Dr. Therapist",
        specialty="Physiotherapy",
        city="Kathmandu",
        gender="Male",
        rating=4.5,
        reviews=10,
        price=1500.0,
        experience=5,
        bio="Experienced physiotherapist",
        createdAt=NOW,
        updatedAt=NOW,
    ),
)


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


class TestListTherapistsAdmin:
    def test_list_therapists(self, admin_client, mock_db):
        mock_db.user.count.return_value = 1
        mock_db.user.find_many.return_value = [MOCK_THERAPIST_USER_WITH_PROFILE]
        mock_db.session.count.return_value = 5

        response = admin_client.get("/api/v1/admin/therapists")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["name"] == "Test Therapist"
        assert body["items"][0]["specialty"] == "Physiotherapy"
        assert body["items"][0]["sessions"] == 5
        assert body["items"][0]["status"] == "Verified"

    def test_list_therapists_with_pagination(self, admin_client, mock_db):
        mock_db.user.count.return_value = 20
        mock_db.user.find_many.return_value = [MOCK_THERAPIST_USER_WITH_PROFILE]
        mock_db.session.count.return_value = 3

        response = admin_client.get("/api/v1/admin/therapists?skip=0&limit=10")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 20
        assert len(body["items"]) == 1

    def test_list_therapists_with_search(self, admin_client, mock_db):
        mock_db.user.count.return_value = 1
        mock_db.user.find_many.return_value = [MOCK_THERAPIST_USER_WITH_PROFILE]
        mock_db.session.count.return_value = 0

        response = admin_client.get("/api/v1/admin/therapists?search=Test")

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_therapists_empty(self, admin_client, mock_db):
        mock_db.user.count.return_value = 0
        mock_db.user.find_many.return_value = []

        response = admin_client.get("/api/v1/admin/therapists")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_therapists_forbidden_for_non_admin(self, patient_client):
        response = patient_client.get("/api/v1/admin/therapists")
        assert response.status_code == 403


class TestUpdateTherapistAdmin:
    def test_update_therapist(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_USER_WITH_PROFILE.therapist
        mock_db.therapist.update.return_value = MOCK_THERAPIST_USER_WITH_PROFILE.therapist
        mock_db.user.update.return_value = MOCK_THERAPIST_USER_WITH_PROFILE
        mock_db.user.find_unique.return_value = MOCK_THERAPIST_USER_WITH_PROFILE
        mock_db.session.count.return_value = 5

        response = admin_client.put(
            "/api/v1/admin/therapists/therapist-1",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == "therapist-1"

    def test_update_therapist_not_found(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = None

        response = admin_client.put(
            "/api/v1/admin/therapists/unknown",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 404

    def test_update_therapist_forbidden_for_non_admin(self, patient_client):
        response = patient_client.put(
            "/api/v1/admin/therapists/therapist-1",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 403


class TestDeleteTherapistAdmin:
    def test_delete_therapist(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_USER_WITH_PROFILE.therapist
        mock_db.therapist.delete.return_value = None
        mock_db.user.delete.return_value = None

        response = admin_client.delete("/api/v1/admin/therapists/therapist-1")

        assert response.status_code == 204

    def test_delete_therapist_not_found(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = None

        response = admin_client.delete("/api/v1/admin/therapists/unknown")

        assert response.status_code == 404

    def test_delete_therapist_forbidden_for_non_admin(self, patient_client):
        response = patient_client.delete("/api/v1/admin/therapists/therapist-1")
        assert response.status_code == 403


MOCK_PATIENT_WITH_SESSIONS = SimpleNamespace(
    id="patient-1",
    name="Test Patient",
    email="patient@test.com",
    password="$2b$12$LJ3m4ys3Lk0TSwHlOR./YuVF4vj4G.hC3sVJfFJkVixRClvD1zBWe",
    role="PATIENT",
    city="Kathmandu",
    phone="9800000001",
    specialty=None,
    status="APPROVED",
    referralCode="SAHA-TEST1234",
    createdAt=NOW,
    updatedAt=NOW,
)

MOCK_SESSION_FOR_PATIENT = SimpleNamespace(
    id="session-1",
    therapistId="therapist-1",
    patientId="patient-1",
    date=NOW,
    time="10:00",
    type="HOME_VISIT",
    status="COMPLETED",
    address="Test Address",
    fee=1500.0,
    notes=None,
    createdAt=NOW,
    updatedAt=NOW,
    therapist=MOCK_THERAPIST_USER_WITH_PROFILE.therapist,
)


class TestListPatientsAdmin:
    def test_list_patients(self, admin_client, mock_db):
        mock_db.user.count.return_value = 1
        mock_db.user.find_many.return_value = [MOCK_PATIENT_WITH_SESSIONS]
        mock_db.session.find_many.return_value = [MOCK_SESSION_FOR_PATIENT]

        response = admin_client.get("/api/v1/admin/patients")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["name"] == "Test Patient"
        assert body["items"][0]["sessions"] == 1
        assert body["items"][0]["therapist"] == "Dr. Therapist"
        assert body["items"][0]["isActive"] is True

    def test_list_patients_with_pagination(self, admin_client, mock_db):
        mock_db.user.count.return_value = 20
        mock_db.user.find_many.return_value = [MOCK_PATIENT_WITH_SESSIONS]
        mock_db.session.find_many.return_value = []

        response = admin_client.get("/api/v1/admin/patients?skip=0&limit=10")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 20
        assert len(body["items"]) == 1

    def test_list_patients_with_search(self, admin_client, mock_db):
        mock_db.user.count.return_value = 1
        mock_db.user.find_many.return_value = [MOCK_PATIENT_WITH_SESSIONS]
        mock_db.session.find_many.return_value = []

        response = admin_client.get("/api/v1/admin/patients?search=Test")

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_patients_empty(self, admin_client, mock_db):
        mock_db.user.count.return_value = 0
        mock_db.user.find_many.return_value = []

        response = admin_client.get("/api/v1/admin/patients")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_patients_forbidden_for_non_admin(self, patient_client):
        response = patient_client.get("/api/v1/admin/patients")
        assert response.status_code == 403


class TestUpdatePatientAdmin:
    def test_update_patient(self, admin_client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT_WITH_SESSIONS
        mock_db.session.find_many.return_value = []

        response = admin_client.put(
            "/api/v1/admin/patients/patient-1",
            json={"name": "Updated Patient"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == "patient-1"

    def test_update_patient_not_found(self, admin_client, mock_db):
        mock_db.user.find_unique.return_value = None

        response = admin_client.put(
            "/api/v1/admin/patients/unknown",
            json={"name": "Updated"},
        )

        assert response.status_code == 404

    def test_update_patient_forbidden_for_non_admin(self, patient_client):
        response = patient_client.put(
            "/api/v1/admin/patients/patient-1",
            json={"name": "Updated"},
        )
        assert response.status_code == 403


class TestDeletePatientAdmin:
    def test_delete_patient(self, admin_client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT_WITH_SESSIONS
        mock_db.user.delete.return_value = None

        response = admin_client.delete("/api/v1/admin/patients/patient-1")

        assert response.status_code == 204

    def test_delete_patient_not_found(self, admin_client, mock_db):
        mock_db.user.find_unique.return_value = None

        response = admin_client.delete("/api/v1/admin/patients/unknown")

        assert response.status_code == 404

    def test_delete_patient_forbidden_for_non_admin(self, patient_client):
        response = patient_client.delete("/api/v1/admin/patients/patient-1")
        assert response.status_code == 403
