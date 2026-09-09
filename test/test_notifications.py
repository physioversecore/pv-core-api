"""The per-user notification feed.

Read scoping matters most here: a notification is addressed to one account,
so listing and marking must never cross accounts.
"""
from .conftest import MOCK_NOTIFICATION


class TestListNotifications:
    def test_requires_authentication(self, client):
        assert client.get("/api/v1/notifications").status_code == 401

    def test_patient_sees_their_feed_with_an_unread_count(
        self, patient_client, mock_db
    ):
        mock_db.notification.find_many.return_value = [MOCK_NOTIFICATION]
        mock_db.notification.count.return_value = 1

        response = patient_client.get("/api/v1/notifications")

        assert response.status_code == 200
        body = response.json()
        assert len(body["notifications"]) == 1
        assert body["notifications"][0]["id"] == "notification-1"
        assert body["unread"] == 1

    def test_the_feed_is_role_agnostic(self, therapist_client, mock_db):
        mock_db.notification.find_many.return_value = []
        mock_db.notification.count.return_value = 0

        assert therapist_client.get("/api/v1/notifications").status_code == 200


class TestMarkRead:
    def test_requires_authentication(self, client):
        assert client.post("/api/v1/notifications/abc/read").status_code == 401

    def test_marks_an_own_notification_read(self, patient_client, mock_db):
        mock_db.notification.find_first.return_value = MOCK_NOTIFICATION
        mock_db.notification.update.return_value = MOCK_NOTIFICATION

        response = patient_client.post("/api/v1/notifications/notification-1/read")

        assert response.status_code == 200

    def test_someone_elses_notification_is_404_not_a_silent_write(
        self, patient_client, mock_db
    ):
        # The service scopes the lookup by user, so a row belonging to another
        # account simply is not found.
        mock_db.notification.find_first.return_value = None

        response = patient_client.post("/api/v1/notifications/notification-1/read")

        assert response.status_code == 404
        mock_db.notification.update.assert_not_called()

    def test_read_all_requires_authentication(self, client):
        assert client.post("/api/v1/notifications/read-all").status_code == 401

    def test_read_all_succeeds(self, patient_client, mock_db):
        mock_db.notification.update_many.return_value = 3

        assert patient_client.post("/api/v1/notifications/read-all").status_code == 204


class TestCreate:
    def test_patients_cannot_create_notifications(self, patient_client):
        response = patient_client.post(
            "/api/v1/notifications",
            json={"userId": "u1", "type": "TEST", "title": "t", "body": "b"},
        )
        assert response.status_code == 403

    def test_admin_can_create(self, admin_client, mock_db):
        mock_db.notification.create.return_value = MOCK_NOTIFICATION

        response = admin_client.post(
            "/api/v1/notifications",
            json={
                "userId": "patient-1",
                "type": "SESSION_BOOKED",
                "title": "Booking confirmed",
                "body": "Your session is confirmed.",
            },
        )

        assert response.status_code == 201
        assert response.json()["id"] == "notification-1"
