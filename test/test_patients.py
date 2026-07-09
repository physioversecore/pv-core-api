from unittest.mock import patch

from .conftest import MOCK_PATIENT, MOCK_SESSION, MOCK_THERAPIST_PROFILE


class TestPatientDashboard:
    def test_dashboard_success(self, patient_client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT
        mock_db.session.count.return_value = 5
        mock_db.session.find_first.return_value = MOCK_SESSION
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        response = patient_client.get("/api/v1/patients/me/dashboard")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Test Patient"
        assert body["totalSessions"] == 5
        assert body["completedSessions"] == 5
        assert body["upcomingSessions"] == 5
        assert body["referralCode"] == "SAHA-TEST1234"
        assert body["referralLink"] == "https://sahayatri.np/r/SAHA-TEST1234"
        assert body["nextSession"]["therapistName"] == "Dr. Therapist"
        assert body["nextSession"]["therapistId"] == "therapist-1"

    def test_dashboard_no_sessions(self, patient_client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT
        mock_db.session.count.return_value = 0
        mock_db.session.find_first.return_value = None

        response = patient_client.get("/api/v1/patients/me/dashboard")

        assert response.status_code == 200
        body = response.json()
        assert body["totalSessions"] == 0
        assert body["completedSessions"] == 0
        assert body["upcomingSessions"] == 0
        assert body["nextSession"] is None

    def test_dashboard_generates_referral_code(self, patient_client, mock_db):
        patient_no_ref = MOCK_PATIENT.__class__(
            id=MOCK_PATIENT.id,
            name=MOCK_PATIENT.name,
            email=MOCK_PATIENT.email,
            password=MOCK_PATIENT.password,
            role=MOCK_PATIENT.role,
            city=MOCK_PATIENT.city,
            phone=MOCK_PATIENT.phone,
            specialty=MOCK_PATIENT.specialty,
            status=MOCK_PATIENT.status,
            referralCode=None,
            createdAt=MOCK_PATIENT.createdAt,
            updatedAt=MOCK_PATIENT.updatedAt,
        )

        def find_unique_side_effect(*, where):
            if where.get("id") == patient_no_ref.id:
                return patient_no_ref
            return None

        mock_db.user.find_unique.side_effect = find_unique_side_effect
        mock_db.user.update.return_value = patient_no_ref
        mock_db.session.count.return_value = 0
        mock_db.session.find_first.return_value = None

        with patch("app.services.patient.generate_referral_code", return_value="SAHA-FRESH123"):
            response = patient_client.get("/api/v1/patients/me/dashboard")

        assert response.status_code == 200
        body = response.json()
        assert body["referralCode"] == "SAHA-FRESH123"
        assert body["referralLink"] == "https://sahayatri.np/r/SAHA-FRESH123"
        mock_db.user.update.assert_called_once()

    def test_dashboard_requires_auth(self, client):
        response = client.get("/api/v1/patients/me/dashboard")
        assert response.status_code == 401


class TestPatientReferral:
    def test_referral_success(self, patient_client, mock_db):
        mock_db.user.find_unique.return_value = MOCK_PATIENT

        response = patient_client.get("/api/v1/patients/me/referral")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SAHA-TEST1234"
        assert body["link"] == "https://sahayatri.np/r/SAHA-TEST1234"

    def test_referral_generates_code(self, patient_client, mock_db):
        patient_no_ref = MOCK_PATIENT.__class__(
            id=MOCK_PATIENT.id,
            name=MOCK_PATIENT.name,
            email=MOCK_PATIENT.email,
            password=MOCK_PATIENT.password,
            role=MOCK_PATIENT.role,
            city=MOCK_PATIENT.city,
            phone=MOCK_PATIENT.phone,
            specialty=MOCK_PATIENT.specialty,
            status=MOCK_PATIENT.status,
            referralCode=None,
            createdAt=MOCK_PATIENT.createdAt,
            updatedAt=MOCK_PATIENT.updatedAt,
        )

        def find_unique_side_effect(*, where):
            if where.get("id") == patient_no_ref.id:
                return patient_no_ref
            return None

        mock_db.user.find_unique.side_effect = find_unique_side_effect
        mock_db.user.update.return_value = patient_no_ref

        with patch("app.services.patient.generate_referral_code", return_value="SAHA-NEWCODE"):
            response = patient_client.get("/api/v1/patients/me/referral")

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SAHA-NEWCODE"
        assert body["link"] == "https://sahayatri.np/r/SAHA-NEWCODE"
        mock_db.user.update.assert_called_once()

    def test_referral_requires_auth(self, client):
        response = client.get("/api/v1/patients/me/referral")
        assert response.status_code == 401
