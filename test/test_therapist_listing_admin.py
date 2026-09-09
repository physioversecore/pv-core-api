"""Who may change a therapist's listing.

Coverage and information-only listings are only useful if someone can set
them over the API. The split: therapists describe their own reach, while the
platform decides whether they can be booked at all.
"""
from datetime import datetime


class TestSelfServiceableFields:
    def test_a_therapist_can_set_their_own_coverage(
        self, therapist_client, mock_db
    ):
        mock_db.therapist.find_unique.return_value = _row()
        mock_db.therapist.update.return_value = _row(lat=27.7, radius=7)

        response = therapist_client.put(
            "/api/v1/therapists/t1",
            json={"latitude": 27.7, "longitude": 85.3, "serviceRadiusKm": 7},
        )

        assert response.status_code == 200
        sent = mock_db.therapist.update.call_args.kwargs["data"]
        assert sent["serviceRadiusKm"] == 7


class TestRestrictedFields:
    def test_a_therapist_may_not_make_themselves_information_only(
        self, therapist_client, mock_db
    ):
        # Otherwise a therapist could quietly opt out of taking bookings.
        mock_db.therapist.find_unique.return_value = _row()

        response = therapist_client.put(
            "/api/v1/therapists/t1", json={"listingType": "INFO_ONLY"}
        )

        assert response.status_code == 403
        mock_db.therapist.update.assert_not_called()

    def test_a_therapist_may_not_claim_a_clinic(self, therapist_client, mock_db):
        mock_db.therapist.find_unique.return_value = _row()

        response = therapist_client.put(
            "/api/v1/therapists/t1", json={"clinicId": "c1"}
        )

        assert response.status_code == 403

    def test_an_admin_can_set_both(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = _row(user_id="someone-else")
        mock_db.therapist.update.return_value = _row(
            user_id="someone-else", listing="INFO_ONLY"
        )

        response = admin_client.put(
            "/api/v1/therapists/t1",
            json={"listingType": "INFO_ONLY", "clinicId": "c1"},
        )

        assert response.status_code == 200
        sent = mock_db.therapist.update.call_args.kwargs["data"]
        assert sent["listingType"] == "INFO_ONLY"
        assert sent["clinicId"] == "c1"

    def test_an_unknown_listing_type_is_rejected(self, admin_client, mock_db):
        mock_db.therapist.find_unique.return_value = _row(user_id="someone-else")

        response = admin_client.put(
            "/api/v1/therapists/t1", json={"listingType": "MAYBE"}
        )

        assert response.status_code == 400
        mock_db.therapist.update.assert_not_called()


def _row(*, user_id="therapist-user-1", lat=None, radius=None, listing="BOOKABLE"):
    return type(
        "T",
        (),
        {
            "id": "t1",
            "userId": user_id,
            "name": "Dr. Test",
            "specialty": "Sports",
            "city": "Lalitpur",
            "gender": "M",
            "rating": 4.5,
            "reviews": 10,
            "price": 1500.0,
            "experience": 5,
            "bio": "",
            "listingType": listing,
            "clinic": None,
            "latitude": lat,
            "longitude": None,
            "serviceRadiusKm": radius,
            "createdAt": datetime(2026, 1, 1),
            "updatedAt": datetime(2026, 1, 1),
        },
    )()
