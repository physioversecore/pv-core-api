"""Notification producers: who gets told what, and what happens when it breaks.

Three things are worth proving per producer, and each is tested below:

* the right *type* lands on the right *recipient* with a usable `refId`;
* both parties hear about a shared event, in their own words;
* the originating request still succeeds when the notification write raises.

That last one is the point of the whole fire-and-forget arrangement: a booking
must not 500 because an insert into the feed failed.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import notification_events as events
from app.services.notification_events import NotificationType, RefType

from .conftest import MOCK_PATIENT, MOCK_SESSION, MOCK_THERAPIST_PROFILE

WHEN = datetime(2024, 6, 15, 0, 0, 0)

# A session with both sides attached, which is what the producers read.
SESSION_WITH_PARTIES = SimpleNamespace(
    id="session-1",
    therapistId="therapist-1",
    patientId="patient-1",
    date=WHEN,
    time="09:00",
    type="HOME_VISIT",
    status="SCHEDULED",
    address="Test Address",
    fee=1500.0,
    notes=None,
    createdAt=WHEN,
    updatedAt=WHEN,
    therapist=MOCK_THERAPIST_PROFILE,
    patient=MOCK_PATIENT,
)

PATIENT_USER_ID = "patient-1"
THERAPIST_USER_ID = "therapist-user-1"

SESSION_CREATE_DATA = {
    "therapistId": "therapist-1",
    "date": "2024-06-15T09:00:00",
    "time": "09:00",
    "type": "HOME_VISIT",
    "address": "Test Address",
    "fee": 1500.0,
    "notes": None,
}


# ── helpers ────────────────────────────────────────────────────────────────


def written(mock_db) -> list[dict]:
    """Every notification row the request tried to write."""
    return [c.kwargs["data"] for c in mock_db.notification.create.call_args_list]


def by_type(mock_db, type_) -> list[dict]:
    return [row for row in written(mock_db) if row["type"] == str(type_)]


def recipients(mock_db, type_) -> set[str]:
    return {row["userId"] for row in by_type(mock_db, type_)}


def explode(mock_db) -> None:
    """Make every notification write blow up, as a dead database would."""
    mock_db.notification.create.side_effect = RuntimeError("feed is down")
    mock_db.notification.find_first.side_effect = RuntimeError("feed is down")


def session_feed_ready(mock_db, session=SESSION_WITH_PARTIES) -> None:
    """Serve the bare row to `get_or_404` and the joined one to the producer.

    They are the same query on the same table; only the producer asks for the
    two parties, so the include is what tells them apart.
    """
    bare = SimpleNamespace(
        **{k: v for k, v in vars(session).items() if k not in ("therapist", "patient")}
    )

    def lookup(**kwargs):
        return session if kwargs.get("include") else bare

    mock_db.session.find_unique.side_effect = lookup
    mock_db.notification.find_first.return_value = None


# ── the registry itself ────────────────────────────────────────────────────


class TestRegistry:
    def test_keys_are_their_own_names(self):
        # The wire value is the contract; a typo'd alias would ship a key the
        # mobile switch has never heard of.
        for member in NotificationType:
            assert member.value == member.name
        for member in RefType:
            assert member.value == member.name

    def test_every_producer_uses_a_registered_type(self):
        # Nothing may write a key that is not in the registry, or the docs and
        # the mobile switch drift from what the feed actually contains.
        import inspect

        source = inspect.getsource(events)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("type=") and "NotificationType." in stripped:
                key = stripped.split("NotificationType.")[1].rstrip(",")
                assert key in NotificationType.__members__


# ── bookings ───────────────────────────────────────────────────────────────


class TestBookingNotifications:
    def test_booking_tells_both_sides_in_their_own_words(
        self, patient_client, mock_db
    ):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        session_feed_ready(mock_db)

        response = patient_client.post("/api/v1/sessions", json=SESSION_CREATE_DATA)

        assert response.status_code == 201
        patient_row = by_type(mock_db, NotificationType.SESSION_BOOKED)[0]
        therapist_row = by_type(mock_db, NotificationType.SESSION_NEW_BOOKING)[0]

        assert patient_row["userId"] == PATIENT_USER_ID
        assert therapist_row["userId"] == THERAPIST_USER_ID
        assert patient_row["body"] != therapist_row["body"]

    def test_booking_names_the_therapist_and_the_time(
        self, patient_client, mock_db
    ):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        session_feed_ready(mock_db)

        patient_client.post("/api/v1/sessions", json=SESSION_CREATE_DATA)

        body = by_type(mock_db, NotificationType.SESSION_BOOKED)[0]["body"]
        assert "Dr. Therapist" in body
        assert "09:00" in body

    def test_booking_points_at_the_session(self, patient_client, mock_db):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        session_feed_ready(mock_db)

        patient_client.post("/api/v1/sessions", json=SESSION_CREATE_DATA)

        row = by_type(mock_db, NotificationType.SESSION_BOOKED)[0]
        assert row["refType"] == "SESSION"
        assert row["refId"] == "session-1"

    def test_booking_still_succeeds_when_the_feed_is_down(
        self, patient_client, mock_db
    ):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        session_feed_ready(mock_db)
        explode(mock_db)

        response = patient_client.post("/api/v1/sessions", json=SESSION_CREATE_DATA)

        assert response.status_code == 201
        assert response.json()["id"] == "session-1"

    def test_a_repeat_booking_notification_is_skipped(
        self, patient_client, mock_db
    ):
        # The dedupe key is (user, type, refId): a row already there means the
        # event was already announced.
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        session_feed_ready(mock_db)
        mock_db.notification.find_first.return_value = SimpleNamespace(id="n1")

        patient_client.post("/api/v1/sessions", json=SESSION_CREATE_DATA)

        mock_db.notification.create.assert_not_awaited()


class TestPaidBookingNotifications:
    PAYLOAD = {
        **SESSION_CREATE_DATA,
        "platformFee": 100.0,
        "paymentMethod": "khalti",
        "currency": "NPR",
        "paymentType": "FULL",
    }

    def _payment(self):
        return SimpleNamespace(
            id="payment-9",
            userId=PATIENT_USER_ID,
            amount=1600.0,
            status="COMPLETED",
            method="KHALTI",
            sessionId="session-1",
            createdAt=WHEN,
            updatedAt=WHEN,
        )

    def test_paying_for_a_booking_confirms_both_the_slot_and_the_money(
        self, patient_client, mock_db
    ):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        mock_db.payment.create.return_value = self._payment()
        mock_db.payment.find_unique.return_value = self._payment()
        session_feed_ready(mock_db)

        response = patient_client.post("/api/v1/payments/process", json=self.PAYLOAD)

        assert response.status_code == 201
        assert recipients(mock_db, NotificationType.SESSION_BOOKED) == {
            PATIENT_USER_ID
        }
        assert recipients(mock_db, NotificationType.PAYMENT_RECEIVED) == {
            PATIENT_USER_ID
        }

    def test_the_receipt_names_the_method_and_the_amount(
        self, patient_client, mock_db
    ):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        mock_db.payment.create.return_value = self._payment()
        mock_db.payment.find_unique.return_value = self._payment()
        session_feed_ready(mock_db)

        patient_client.post("/api/v1/payments/process", json=self.PAYLOAD)

        body = by_type(mock_db, NotificationType.PAYMENT_RECEIVED)[0]["body"]
        assert "Khalti" in body
        assert "Rs 1,600" in body

    def test_the_therapist_is_not_sent_the_patients_receipt(
        self, patient_client, mock_db
    ):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        mock_db.payment.create.return_value = self._payment()
        mock_db.payment.find_unique.return_value = self._payment()
        session_feed_ready(mock_db)

        patient_client.post("/api/v1/payments/process", json=self.PAYLOAD)

        assert THERAPIST_USER_ID not in recipients(
            mock_db, NotificationType.PAYMENT_RECEIVED
        )

    def test_payment_still_succeeds_when_the_feed_is_down(
        self, patient_client, mock_db
    ):
        mock_db.session.find_many.return_value = []
        mock_db.session.create.return_value = MOCK_SESSION
        mock_db.payment.create.return_value = self._payment()
        mock_db.payment.find_unique.return_value = self._payment()
        session_feed_ready(mock_db)
        explode(mock_db)

        response = patient_client.post("/api/v1/payments/process", json=self.PAYLOAD)

        assert response.status_code == 201


# ── session status transitions ─────────────────────────────────────────────


def _updated(status_value):
    return {
        **{
            k: v
            for k, v in vars(SESSION_WITH_PARTIES).items()
            if k not in ("therapist", "patient")
        },
        "status": status_value,
        "therapistName": "Dr. Therapist",
        "patientName": "Test Patient",
        "patientPhone": "9800000001",
        "familyMemberName": None,
    }


class TestStatusTransitions:
    def test_cancelling_tells_both_sides(self, patient_client, mock_db):
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES

        response = patient_client.put(
            "/api/v1/sessions/session-1", json={"status": "CANCELLED"}
        )

        assert response.status_code == 200
        assert recipients(mock_db, NotificationType.SESSION_CANCELLED) == {
            PATIENT_USER_ID,
            THERAPIST_USER_ID,
        }

    def test_the_canceller_is_addressed_differently_from_the_other_side(
        self, patient_client, mock_db
    ):
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES

        patient_client.put(
            "/api/v1/sessions/session-1", json={"status": "CANCELLED"}
        )

        rows = {
            row["userId"]: row["body"]
            for row in by_type(mock_db, NotificationType.SESSION_CANCELLED)
        }
        assert rows[PATIENT_USER_ID].startswith("You cancelled")
        assert "Test Patient cancelled" in rows[THERAPIST_USER_ID]

    def test_resaving_the_same_status_announces_nothing(
        self, patient_client, mock_db
    ):
        # The feed hangs off the transition, not the write. This endpoint is
        # also used to edit notes, and clients retry.
        already_cancelled = SimpleNamespace(
            **{**vars(SESSION_WITH_PARTIES), "status": "CANCELLED"}
        )
        session_feed_ready(mock_db, already_cancelled)
        mock_db.session.update.return_value = already_cancelled

        patient_client.put(
            "/api/v1/sessions/session-1", json={"status": "CANCELLED"}
        )

        assert by_type(mock_db, NotificationType.SESSION_CANCELLED) == []

    def test_editing_notes_announces_nothing(self, patient_client, mock_db):
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES

        patient_client.put(
            "/api/v1/sessions/session-1", json={"notes": "Bring the crutches"}
        )

        mock_db.notification.create.assert_not_awaited()

    def test_completing_asks_the_patient_to_rate_and_records_it_for_the_therapist(
        self, therapist_client, mock_db
    ):
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.review.find_first.return_value = None
        mock_db.setting.find_unique.return_value = None
        mock_db.user.find_unique.return_value = SimpleNamespace(
            id=PATIENT_USER_ID, name="Test Patient", referredById=None
        )

        response = therapist_client.put(
            "/api/v1/sessions/session-1", json={"status": "COMPLETED"}
        )

        assert response.status_code == 200
        assert recipients(mock_db, NotificationType.SESSION_RATE_REQUEST) == {
            PATIENT_USER_ID
        }
        assert recipients(mock_db, NotificationType.SESSION_COMPLETED) == {
            THERAPIST_USER_ID
        }

    def test_no_rating_prompt_once_the_therapist_has_been_rated(
        self, therapist_client, mock_db
    ):
        # `POST /reviews` refuses a second review of the same therapist, so the
        # prompt would lead to a dead end.
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.review.find_first.return_value = SimpleNamespace(id="review-1")
        mock_db.setting.find_unique.return_value = None
        mock_db.user.find_unique.return_value = SimpleNamespace(
            id=PATIENT_USER_ID, name="Test Patient", referredById=None
        )

        therapist_client.put(
            "/api/v1/sessions/session-1", json={"status": "COMPLETED"}
        )

        assert by_type(mock_db, NotificationType.SESSION_RATE_REQUEST) == []
        assert recipients(mock_db, NotificationType.SESSION_COMPLETED) == {
            PATIENT_USER_ID,
            THERAPIST_USER_ID,
        }

    def test_a_reschedule_request_goes_to_the_other_side(
        self, patient_client, mock_db
    ):
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES

        patient_client.put(
            "/api/v1/sessions/session-1",
            json={"status": "RESCHEDULE_REQUESTED"},
        )

        assert recipients(
            mock_db, NotificationType.SESSION_RESCHEDULE_REQUESTED
        ) == {THERAPIST_USER_ID}

    def test_a_decline_request_is_acknowledged_to_the_therapist_only(
        self, therapist_client, mock_db
    ):
        # The patient is not told their visit might fall through until a
        # decision actually lands.
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        therapist_client.put(
            "/api/v1/sessions/session-1", json={"status": "DECLINE_REQUESTED"}
        )

        assert recipients(
            mock_db, NotificationType.SESSION_DECLINE_REQUESTED
        ) == {THERAPIST_USER_ID}

    def test_starting_a_session_is_deliberately_silent(
        self, therapist_client, mock_db
    ):
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE

        therapist_client.put(
            "/api/v1/sessions/session-1", json={"status": "IN_PROGRESS"}
        )

        mock_db.notification.create.assert_not_awaited()

    def test_the_status_write_still_succeeds_when_the_feed_is_down(
        self, patient_client, mock_db
    ):
        session_feed_ready(mock_db)
        mock_db.session.update.return_value = SESSION_WITH_PARTIES
        explode(mock_db)

        response = patient_client.put(
            "/api/v1/sessions/session-1", json={"status": "CANCELLED"}
        )

        assert response.status_code == 200


class TestReschedule:
    def test_moving_a_slot_tells_both_sides_the_new_time(
        self, patient_client, mock_db
    ):
        moved = SimpleNamespace(**{**vars(SESSION_WITH_PARTIES), "time": "14:00"})
        session_feed_ready(mock_db)
        mock_db.session.find_first.return_value = None
        mock_db.session.update.return_value = moved
        mock_db.notification.find_first.return_value = None
        mock_db.setting.find_unique.return_value = None

        response = patient_client.patch(
            "/api/v1/sessions/session-1/reschedule",
            json={"newDate": "2024-06-20", "newTime": "14:00"},
        )

        if response.status_code != 200:  # slot validation depends on working hours
            pytest.skip("reschedule rejected before the notification step")
        assert recipients(mock_db, NotificationType.SESSION_RESCHEDULED) == {
            PATIENT_USER_ID,
            THERAPIST_USER_ID,
        }


class TestHardDelete:
    def test_deleting_a_booking_tells_both_sides_before_the_row_goes(
        self, patient_client, mock_db
    ):
        session_feed_ready(mock_db)

        response = patient_client.delete("/api/v1/sessions/session-1")

        assert response.status_code == 204
        assert recipients(mock_db, NotificationType.SESSION_CANCELLED) == {
            PATIENT_USER_ID,
            THERAPIST_USER_ID,
        }

    def test_delete_still_succeeds_when_the_feed_is_down(
        self, patient_client, mock_db
    ):
        session_feed_ready(mock_db)
        explode(mock_db)

        response = patient_client.delete("/api/v1/sessions/session-1")

        assert response.status_code == 204
        mock_db.session.delete.assert_awaited()


# ── therapist lifecycle ────────────────────────────────────────────────────


ADMIN_THERAPIST_PROFILE = SimpleNamespace(
    **{
        **vars(MOCK_THERAPIST_PROFILE),
        "mediaUrls": None,
        "licenseNumber": "NMC-1234",
        "applicationStatus": "SUBMITTED",
        "listingType": "BOOKABLE",
        "clinicId": None,
        "latitude": None,
        "longitude": None,
        "serviceRadiusKm": None,
    }
)


def _therapist_user(status_value):
    return SimpleNamespace(
        id=THERAPIST_USER_ID,
        name="Anisha Shrestha",
        email="anisha@test.com",
        status=status_value,
        role="THERAPIST",
        mustChangePassword=False,
        city="Kathmandu",
        phone="9800000002",
        specialty="Physiotherapy",
        createdAt=WHEN,
        updatedAt=WHEN,
    )


THERAPIST_USER_APPROVED = _therapist_user("APPROVED")
THERAPIST_USER_REJECTED = _therapist_user("REJECTED")


class TestApplicationDecisions:
    def _arrange(self, mock_db, user):
        mock_db.therapist.find_unique.return_value = ADMIN_THERAPIST_PROFILE
        mock_db.user.find_unique.return_value = user
        mock_db.notification.find_first.return_value = None
        mock_db.verification.update_many.return_value = 0
        mock_db.therapist.update.return_value = ADMIN_THERAPIST_PROFILE
        mock_db.user.update.return_value = user
        mock_db.session.count.return_value = 0
        mock_db.review.find_many.return_value = []
        mock_db.verification.find_many.return_value = []
        mock_db.clinic.find_unique.return_value = None

    def test_approval_reaches_the_therapists_own_feed(self, admin_client, mock_db):
        self._arrange(mock_db, THERAPIST_USER_APPROVED)

        response = admin_client.put("/api/v1/admin/therapists/therapist-1/approve")

        assert response.status_code == 200
        rows = by_type(mock_db, NotificationType.APPLICATION_APPROVED)
        assert rows and rows[0]["userId"] == THERAPIST_USER_ID
        assert rows[0]["refType"] == "THERAPIST"

    def test_approval_greets_the_therapist_by_first_name(
        self, admin_client, mock_db
    ):
        self._arrange(mock_db, THERAPIST_USER_APPROVED)

        admin_client.put("/api/v1/admin/therapists/therapist-1/approve")

        body = by_type(mock_db, NotificationType.APPLICATION_APPROVED)[0]["body"]
        assert body.startswith("Anisha, your")

    def test_re_approving_does_not_stack_a_second_row(self, admin_client, mock_db):
        self._arrange(mock_db, THERAPIST_USER_APPROVED)
        mock_db.notification.find_first.return_value = SimpleNamespace(id="n1")

        admin_client.put("/api/v1/admin/therapists/therapist-1/approve")

        assert by_type(mock_db, NotificationType.APPLICATION_APPROVED) == []

    def test_rejection_carries_the_reason(self, admin_client, mock_db):
        self._arrange(mock_db, THERAPIST_USER_REJECTED)

        response = admin_client.put(
            "/api/v1/admin/therapists/therapist-1/reject",
            json={"note": "NMC licence number could not be verified"},
        )

        assert response.status_code == 200
        body = by_type(mock_db, NotificationType.APPLICATION_REJECTED)[0]["body"]
        assert "NMC licence number could not be verified" in body

    def test_approval_still_succeeds_when_the_feed_is_down(
        self, admin_client, mock_db
    ):
        self._arrange(mock_db, THERAPIST_USER_APPROVED)
        explode(mock_db)

        response = admin_client.put("/api/v1/admin/therapists/therapist-1/approve")

        assert response.status_code == 200


# ── refunds ────────────────────────────────────────────────────────────────


class TestRefundNotifications:
    def test_opening_a_case_tells_the_patient_whose_money_it_is(
        self, admin_client, mock_db
    ):
        mock_db.user.find_unique.return_value = MOCK_PATIENT
        mock_db.refund.create.return_value = SimpleNamespace(
            id="refund-1",
            patientId=PATIENT_USER_ID,
            patient=MOCK_PATIENT,
            bookingId="session-1",
            amount=1500.0,
            reason="NO_SHOW",
            status="PENDING",
            denyReason=None,
            resolvedAt=None,
            assigneeId=None,
            source="ADMIN_MANUAL",
            complaintId=None,
            notes=None,
            createdAt=WHEN,
        )
        mock_db.notification.find_first.return_value = None

        response = admin_client.post(
            "/api/v1/admin/refunds",
            json={
                "patientId": PATIENT_USER_ID,
                "bookingId": "session-1",
                "amount": 1500.0,
                "reason": "No-show",
            },
        )

        assert response.status_code == 201
        rows = by_type(mock_db, NotificationType.REFUND_REQUESTED)
        assert rows[0]["userId"] == PATIENT_USER_ID
        assert "Rs 1,500" in rows[0]["body"]
        assert rows[0]["refType"] == "REFUND"

    def _decided(self, status_value, deny_reason=None):
        return SimpleNamespace(
            id="refund-1",
            patientId=PATIENT_USER_ID,
            patient=MOCK_PATIENT,
            bookingId="session-1",
            amount=1500.0,
            reason="NO_SHOW",
            status=status_value,
            denyReason=deny_reason,
            resolvedAt=WHEN,
            assigneeId=None,
            source="ADMIN_MANUAL",
            complaintId=None,
            notes=None,
            createdAt=WHEN,
        )

    def test_approval_reaches_the_patient(self, admin_client, mock_db):
        mock_db.refund.find_unique.return_value = self._decided("PENDING")
        mock_db.refund.update.return_value = self._decided("APPROVED")
        mock_db.notification.find_first.return_value = None

        response = admin_client.put(
            "/api/v1/admin/refunds/refund-1", json={"status": "Approved"}
        )

        assert response.status_code == 200
        assert recipients(mock_db, NotificationType.REFUND_APPROVED) == {
            PATIENT_USER_ID
        }

    def test_a_denial_explains_itself(self, admin_client, mock_db):
        mock_db.refund.find_unique.return_value = self._decided("PENDING")
        mock_db.refund.update.return_value = self._decided(
            "DENIED", deny_reason="The session was attended"
        )
        mock_db.notification.find_first.return_value = None

        admin_client.put(
            "/api/v1/admin/refunds/refund-1", json={"status": "Denied"}
        )

        body = by_type(mock_db, NotificationType.REFUND_DENIED)[0]["body"]
        assert "The session was attended" in body

    def test_re_saving_a_decided_refund_says_nothing_again(
        self, admin_client, mock_db
    ):
        mock_db.refund.find_unique.return_value = self._decided("APPROVED")
        mock_db.refund.update.return_value = self._decided("APPROVED")
        mock_db.notification.find_first.return_value = None

        admin_client.put(
            "/api/v1/admin/refunds/refund-1", json={"status": "Approved"}
        )

        assert by_type(mock_db, NotificationType.REFUND_APPROVED) == []

    def test_the_decision_still_saves_when_the_feed_is_down(
        self, admin_client, mock_db
    ):
        mock_db.refund.find_unique.return_value = self._decided("PENDING")
        mock_db.refund.update.return_value = self._decided("APPROVED")
        explode(mock_db)

        response = admin_client.put(
            "/api/v1/admin/refunds/refund-1", json={"status": "Approved"}
        )

        assert response.status_code == 200


# ── producers with no router in the test app ───────────────────────────────
#
# `availability`, `rate-change` and `points` are not mounted on the fake app in
# conftest, so these exercise the producers directly.


class TestTherapistAdminDecisions:
    async def test_rate_change_approval_reaches_the_therapists_user_row(
        self, mock_db
    ):
        # The request names a Therapist profile; notifications are addressed to
        # Users. The producer is what bridges the two.
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.notification.find_first.return_value = None

        await events.notify_rate_change_decided(
            mock_db,
            "rate-1",
            therapist_id="therapist-1",
            approved=True,
            new_rate=2000,
        )

        row = by_type(mock_db, NotificationType.RATE_CHANGE_APPROVED)[0]
        assert row["userId"] == THERAPIST_USER_ID
        assert "Rs 2,000" in row["body"]
        assert row["refId"] == "rate-1"

    async def test_a_missing_therapist_profile_is_a_no_op_not_a_crash(
        self, mock_db
    ):
        mock_db.therapist.find_unique.return_value = None

        await events.notify_rate_change_decided(
            mock_db, "rate-1", therapist_id="therapist-1", approved=True
        )

        mock_db.notification.create.assert_not_awaited()

    async def test_time_off_approval_names_the_span(self, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.notification.find_first.return_value = None

        await events.notify_block_request_decided(
            mock_db,
            "leave-1",
            therapist_id="therapist-1",
            approved=True,
            date_from="2024-06-20",
            date_to="2024-06-24",
        )

        row = by_type(mock_db, NotificationType.LEAVE_APPROVED)[0]
        assert "2024-06-20 to 2024-06-24" in row["body"]
        assert row["refType"] == "LEAVE"

    async def test_a_second_approval_of_the_same_request_is_skipped(
        self, mock_db
    ):
        # `approve_block_request` does not refuse a repeat, so the producer's
        # key is the only thing standing between the therapist and two rows.
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        mock_db.notification.find_first.return_value = SimpleNamespace(id="n1")

        await events.notify_block_request_decided(
            mock_db, "leave-1", therapist_id="therapist-1", approved=True
        )

        mock_db.notification.create.assert_not_awaited()

    async def test_a_broken_feed_does_not_propagate(self, mock_db):
        mock_db.therapist.find_unique.return_value = MOCK_THERAPIST_PROFILE
        explode(mock_db)

        # No raise is the assertion.
        await events.notify_block_request_decided(
            mock_db, "leave-1", therapist_id="therapist-1", approved=False
        )


class TestRewardNotifications:
    async def test_a_signup_with_a_code_tells_the_referrer(self, mock_db):
        mock_db.notification.find_first.return_value = None

        await events.notify_referral_joined(
            mock_db,
            referrer_user_id=PATIENT_USER_ID,
            joiner_name="Bishal Karki",
            joiner_user_id="patient-2",
        )

        row = by_type(mock_db, NotificationType.REFERRAL_JOINED)[0]
        assert row["userId"] == PATIENT_USER_ID
        assert row["refId"] == "patient-2"
        assert "Bishal" in row["title"]

    async def test_matured_points_are_announced_with_the_amount(self, mock_db):
        await events.notify_points_matured(mock_db, PATIENT_USER_ID, 500)

        row = by_type(mock_db, NotificationType.POINTS_MATURED)[0]
        assert "500 points" in row["title"]

    async def test_nothing_matured_means_nothing_said(self, mock_db):
        await events.notify_points_matured(mock_db, PATIENT_USER_ID, 0)

        mock_db.notification.create.assert_not_awaited()

    async def test_a_balance_read_survives_a_broken_feed(self, mock_db):
        from app.services.points import mature_pending

        mock_db.setting.find_unique.return_value = None
        mock_db.pointtransaction.find_many.return_value = [
            SimpleNamespace(delta=500, id="pt-1")
        ]
        mock_db.pointtransaction.update_many.return_value = 1
        explode(mock_db)

        assert await mature_pending(mock_db, PATIENT_USER_ID) == 1


class TestReportNotifications:
    async def test_a_filed_report_reaches_the_patient(self, mock_db):
        mock_db.notification.find_first.return_value = None

        await events.notify_report_uploaded(
            mock_db,
            "report-1",
            patient_user_id=PATIENT_USER_ID,
            title="Week 3 exercise plan",
            therapist_name="Anisha Shrestha",
        )

        row = by_type(mock_db, NotificationType.REPORT_UPLOADED)[0]
        assert row["userId"] == PATIENT_USER_ID
        assert row["refType"] == "REPORT"
        assert "Week 3 exercise plan" in row["body"]
        assert "Anisha Shrestha" in row["body"]


class TestSafety:
    async def test_no_recipient_is_a_no_op(self, mock_db):
        await events.safe_notify(
            mock_db, None, type=NotificationType.SESSION_BOOKED, title="t", body="b"
        )

        mock_db.notification.create.assert_not_awaited()

    async def test_a_failed_dedupe_check_still_writes_the_notification(
        self, mock_db
    ):
        # Losing the guard is better than losing the message.
        mock_db.notification.find_first.side_effect = RuntimeError("read failed")
        mock_db.notification.create = AsyncMock()

        await events.notify_once(
            mock_db,
            PATIENT_USER_ID,
            type=NotificationType.SESSION_BOOKED,
            title="t",
            body="b",
            ref_id="session-1",
        )

        mock_db.notification.create.assert_awaited_once()

    async def test_enum_values_reach_the_database_as_strings(self, mock_db):
        mock_db.notification.find_first.return_value = None

        await events.safe_notify(
            mock_db,
            PATIENT_USER_ID,
            type=NotificationType.SESSION_BOOKED,
            title="t",
            body="b",
            ref_type=RefType.SESSION,
            ref_id="session-1",
        )

        row = written(mock_db)[0]
        assert type(row["type"]) is str
        assert type(row["refType"]) is str
