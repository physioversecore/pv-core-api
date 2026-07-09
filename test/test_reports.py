from .conftest import MOCK_REPORT, MOCK_PATIENT

REPORT_CREATE_DATA = {
    "patientId": "patient-1",
    "title": "New Report",
    "content": "Report content",
}


class TestCreateReport:
    def test_create_by_therapist(self, therapist_client, mock_db):
        mock_db.report.create.return_value = MOCK_REPORT

        response = therapist_client.post("/api/v1/reports", json=REPORT_CREATE_DATA)

        assert response.status_code == 201
        assert response.json()["id"] == "report-1"

    def test_create_by_admin(self, admin_client, mock_db):
        mock_db.report.create.return_value = MOCK_REPORT

        response = admin_client.post("/api/v1/reports", json=REPORT_CREATE_DATA)

        assert response.status_code == 201

    def test_create_by_patient_forbidden(self, patient_client):
        response = patient_client.post("/api/v1/reports", json=REPORT_CREATE_DATA)

        assert response.status_code == 403


class TestListReports:
    def test_list_as_patient(self, patient_client, mock_db):
        mock_db.report.find_many.return_value = [MOCK_REPORT]

        response = patient_client.get("/api/v1/reports")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "report-1"

    def test_list_as_therapist_with_patient_id(self, therapist_client, mock_db):
        mock_db.report.find_many.return_value = [MOCK_REPORT]

        response = therapist_client.get("/api/v1/reports?patient_id=patient-1")

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_as_therapist_without_patient_id(self, therapist_client):
        response = therapist_client.get("/api/v1/reports")

        assert response.status_code == 400

    def test_list_as_admin(self, admin_client, mock_db):
        mock_db.report.find_many.return_value = [MOCK_REPORT]

        response = admin_client.get("/api/v1/reports?patient_id=patient-1")

        assert response.status_code == 200
        assert len(response.json()) == 1


class TestGetReport:
    def test_get_by_id(self, patient_client, mock_db):
        mock_db.report.find_unique.return_value = MOCK_REPORT

        response = patient_client.get("/api/v1/reports/report-1")

        assert response.status_code == 200
        assert response.json()["id"] == "report-1"

    def test_get_not_found(self, patient_client, mock_db):
        mock_db.report.find_unique.return_value = None

        response = patient_client.get("/api/v1/reports/unknown")

        assert response.status_code == 404


class TestUpdateReport:
    def test_update_by_therapist(self, therapist_client, mock_db):
        mock_db.report.find_unique.return_value = MOCK_REPORT
        mock_db.report.update.return_value = MOCK_REPORT

        response = therapist_client.put(
            "/api/v1/reports/report-1", json={"title": "Updated"}
        )

        assert response.status_code == 200

    def test_update_by_admin(self, admin_client, mock_db):
        mock_db.report.find_unique.return_value = MOCK_REPORT
        mock_db.report.update.return_value = MOCK_REPORT

        response = admin_client.put(
            "/api/v1/reports/report-1", json={"title": "Updated"}
        )

        assert response.status_code == 200

    def test_update_by_patient_forbidden(self, patient_client):
        response = patient_client.put(
            "/api/v1/reports/report-1", json={"title": "Updated"}
        )

        assert response.status_code == 403

    def test_update_not_found(self, therapist_client, mock_db):
        mock_db.report.find_unique.return_value = None

        response = therapist_client.put(
            "/api/v1/reports/unknown", json={"title": "Updated"}
        )

        assert response.status_code == 404


class TestDeleteReport:
    def test_delete_by_therapist(self, therapist_client, mock_db):
        mock_db.report.find_unique.return_value = MOCK_REPORT

        response = therapist_client.delete("/api/v1/reports/report-1")

        assert response.status_code == 204

    def test_delete_by_admin(self, admin_client, mock_db):
        mock_db.report.find_unique.return_value = MOCK_REPORT

        response = admin_client.delete("/api/v1/reports/report-1")

        assert response.status_code == 204

    def test_delete_by_patient_forbidden(self, patient_client):
        response = patient_client.delete("/api/v1/reports/report-1")

        assert response.status_code == 403

    def test_delete_not_found(self, therapist_client, mock_db):
        mock_db.report.find_unique.return_value = None

        response = therapist_client.delete("/api/v1/reports/unknown")

        assert response.status_code == 404
