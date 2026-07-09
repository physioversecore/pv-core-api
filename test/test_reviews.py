from .conftest import MOCK_COMPLETED_SESSION, MOCK_REVIEW


class TestTherapistsToRate:
    def test_list_success(self, patient_client, mock_db):
        mock_db.session.find_many.return_value = [MOCK_COMPLETED_SESSION]

        response = patient_client.get("/api/v1/reviews/therapists-to-rate")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["therapistName"] == "Dr. Therapist"
        assert data[0]["sessionId"] == "session-completed-1"

    def test_empty_list(self, patient_client, mock_db):
        mock_db.session.find_many.return_value = []

        response = patient_client.get("/api/v1/reviews/therapists-to-rate")

        assert response.status_code == 200
        assert response.json() == []


class TestCreateReview:
    def test_create_success(self, patient_client, mock_db):
        mock_db.review.find_unique.return_value = None
        mock_db.session.find_unique.return_value = MOCK_COMPLETED_SESSION
        mock_db.review.create.return_value = MOCK_REVIEW

        response = patient_client.post(
            "/api/v1/reviews",
            json={"sessionId": "session-completed-1", "rating": 5, "comment": "Great therapist"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == "Great therapist"

    def test_missing_session(self, patient_client, mock_db):
        mock_db.review.find_unique.return_value = None
        mock_db.session.find_unique.return_value = None

        response = patient_client.post(
            "/api/v1/reviews",
            json={"sessionId": "nonexistent", "rating": 5, "comment": "Great"},
        )

        assert response.status_code == 404

    def test_invalid_rating(self, patient_client, mock_db):
        response = patient_client.post(
            "/api/v1/reviews",
            json={"sessionId": "session-completed-1", "rating": 6, "comment": "Great"},
        )

        assert response.status_code == 400


class TestListReviews:
    def test_list_success(self, patient_client, mock_db):
        mock_db.review.find_many.return_value = [MOCK_REVIEW]
        mock_db.review.count.return_value = 1

        response = patient_client.get("/api/v1/reviews")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["reviews"]) == 1
        assert data["reviews"][0]["rating"] == 5

    def test_empty_list(self, patient_client, mock_db):
        mock_db.review.find_many.return_value = []
        mock_db.review.count.return_value = 0

        response = patient_client.get("/api/v1/reviews")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["reviews"] == []
