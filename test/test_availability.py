"""Availability reads: the synthesised slot grid, and the bulk "who is free?" call.

Two things are under test here.

**Blocks reaching the grid.** The grid is synthesised from working hours and
only then has stored rows laid over it, so a therapist who never touched their
calendar has no rows to lay over — and used to read fully `open` straight
through approved leave, because `block_range` can only stamp `off` onto rows
that already exist. `TestBlocksReachTheSynthesisedGrid` is that exact case.

**The bulk read.** `GET /availability/slots/bulk` answers for many therapists
in one call, in a fixed number of queries, so discovery does not have to fan
out one request per therapist.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from .conftest import MOCK_THERAPIST_PROFILE

NOW = datetime(2024, 6, 15, 10, 30, 0)

# Far enough ahead that nothing under test is "past" — `nextFree` skips past
# slots, and a test that drifted into the past would start failing on its own.
MON = "2030-03-11"
TUE = "2030-03-12"
WED = "2030-03-13"

# The default grid: 09:00–18:00 at 60-minute steps.
DEFAULT_TIMES = [f"{h:02d}:00" for h in range(9, 18)]


def make_block(
    date_from,
    date_to=None,
    days_of_week="[]",
    parts_of_day="[]",
    reason="Approved leave",
    therapist_id="therapist-1",
    block_id="block-1",
):
    return SimpleNamespace(
        id=block_id,
        therapistId=therapist_id,
        dateFrom=date_from,
        dateTo=date_to or date_from,
        daysOfWeek=days_of_week,
        partsOfDay=parts_of_day,
        reason=reason,
        notify=True,
        createdAt=NOW,
    )


def make_slot_row(date_str, time, status, therapist_id="therapist-1"):
    return SimpleNamespace(
        id=f"slot-{date_str}-{time}",
        therapistId=therapist_id,
        date=date_str,
        time=time,
        status=status,
    )


def make_session_row(date_str, time, therapist_id="therapist-1"):
    return SimpleNamespace(
        id=f"session-{date_str}-{time}",
        therapistId=therapist_id,
        date=datetime.fromisoformat(f"{date_str}T00:00:00"),
        time=time,
        fee=1500.0,
        patient=SimpleNamespace(name="Test Patient", phone="9800000001"),
    )


def make_therapist(
    therapist_id="therapist-1",
    user_id="therapist-user-1",
    listing_type="BOOKABLE",
):
    return SimpleNamespace(
        id=therapist_id,
        userId=user_id,
        name=f"Dr. {therapist_id}",
        listingType=listing_type,
    )


def make_user(user_id="therapist-user-1", status="APPROVED"):
    return SimpleNamespace(id=user_id, status=status, role="THERAPIST")


def wire_slots(
    mock_db,
    *,
    therapist=MOCK_THERAPIST_PROFILE,
    rows=(),
    sessions=(),
    blocks=(),
    working_hours=None,
):
    """Everything `get_slots_for_range` reads, for one therapist."""
    mock_db.therapist.find_unique.return_value = therapist
    mock_db.setting.find_unique.return_value = working_hours
    mock_db.availabilityslot.find_many.return_value = list(rows)
    mock_db.session.find_many.return_value = list(sessions)
    mock_db.availabilityblock.find_many.return_value = list(blocks)


def by_date(body):
    out = {}
    for s in body["slots"]:
        out.setdefault(s["date"], {})[s["time"]] = s["status"]
    return out


class TestBlocksReachTheSynthesisedGrid:
    """The bug: approved leave never reached a calendar that had no rows."""

    def test_block_closes_slots_for_a_therapist_with_no_stored_rows(
        self, patient_client, mock_db
    ):
        # The exact shape of the bug: a therapist who has never edited their
        # calendar (no AvailabilitySlot rows, no working-hours Setting) whose
        # leave request was approved. `block_range` had nothing to stamp, so
        # every slot in the blocked span used to come back `open`.
        wire_slots(mock_db, blocks=[make_block(MON, TUE)])

        response = patient_client.get(
            f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={WED}"
        )

        assert response.status_code == 200
        grid = by_date(response.json())
        assert set(grid) == {MON, TUE, WED}
        for blocked_day in (MON, TUE):
            assert list(grid[blocked_day]) == DEFAULT_TIMES
            assert set(grid[blocked_day].values()) == {"off"}, (
                f"{blocked_day} is inside approved leave and must not read open"
            )
        assert set(grid[WED].values()) == {"open"}

    def test_same_bug_through_the_availability_slots_endpoint(
        self, patient_client, mock_db
    ):
        # Both reads share `get_slots_for_range`; this pins the second caller
        # so a future refactor cannot fix one and leave the other lying.
        wire_slots(mock_db, blocks=[make_block(MON, TUE)])

        response = patient_client.get(
            f"/api/v1/availability/slots?therapist_id=therapist-1"
            f"&from_date={MON}&to_date={WED}"
        )

        assert response.status_code == 200
        grid = by_date(response.json())
        assert set(grid[MON].values()) == {"off"}
        assert set(grid[WED].values()) == {"open"}

    def test_blocks_are_still_returned_beside_the_slots(
        self, patient_client, mock_db
    ):
        # pv-core-web's `useManageAvailability` reads `blocks` to draw the
        # block bands and their reason, which a per-slot `off` cannot carry.
        # Folding blocks in must not remove the array.
        wire_slots(mock_db, blocks=[make_block(MON, TUE, reason="Family leave")])

        body = patient_client.get(
            f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={WED}"
        ).json()

        assert len(body["blocks"]) == 1
        block = body["blocks"][0]
        assert block["dateFrom"] == MON
        assert block["dateTo"] == TUE
        assert block["reason"] == "Family leave"
        assert block["daysOfWeek"] == []
        assert block["partsOfDay"] == []

    def test_part_of_day_block_only_closes_that_part(
        self, patient_client, mock_db
    ):
        wire_slots(
            mock_db, blocks=[make_block(MON, MON, parts_of_day='["morning"]')]
        )

        grid = by_date(
            patient_client.get(
                f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={MON}"
            ).json()
        )

        # morning is 06:00–12:00 for a block.
        assert grid[MON]["09:00"] == "off"
        assert grid[MON]["11:00"] == "off"
        assert grid[MON]["12:00"] == "open"
        assert grid[MON]["17:00"] == "open"

    def test_day_of_week_block_only_closes_those_weekdays(
        self, patient_client, mock_db
    ):
        wire_slots(
            mock_db,
            blocks=[make_block(MON, WED, days_of_week='["Tue"]')],
        )

        grid = by_date(
            patient_client.get(
                f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={WED}"
            ).json()
        )

        assert set(grid[MON].values()) == {"open"}
        assert set(grid[TUE].values()) == {"off"}
        assert set(grid[WED].values()) == {"open"}

    def test_block_closes_a_stored_open_row(self, patient_client, mock_db):
        wire_slots(
            mock_db,
            rows=[make_slot_row(MON, "09:00", "open")],
            blocks=[make_block(MON)],
        )

        grid = by_date(
            patient_client.get(
                f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={MON}"
            ).json()
        )

        assert grid[MON]["09:00"] == "off"

    def test_block_does_not_close_a_booked_slot(self, patient_client, mock_db):
        # `block_range` leaves booked slots alone and reports them as
        # cancellations for a human to confirm. The read must agree: turning a
        # booked slot `off` would hide a session the patient still holds.
        wire_slots(
            mock_db,
            sessions=[make_session_row(MON, "10:00")],
            blocks=[make_block(MON)],
        )

        grid = by_date(
            patient_client.get(
                f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={MON}"
            ).json()
        )

        assert grid[MON]["10:00"] == "booked"
        assert grid[MON]["09:00"] == "off"

    def test_block_does_not_close_a_booked_row_without_a_session(
        self, patient_client, mock_db
    ):
        wire_slots(
            mock_db,
            rows=[make_slot_row(MON, "10:00", "booked")],
            blocks=[make_block(MON)],
        )

        grid = by_date(
            patient_client.get(
                f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={MON}"
            ).json()
        )

        assert grid[MON]["10:00"] == "booked"

    def test_no_blocks_leaves_the_grid_untouched(self, patient_client, mock_db):
        wire_slots(mock_db, rows=[make_slot_row(MON, "09:00", "off")])

        body = patient_client.get(
            f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={TUE}"
        ).json()
        grid = by_date(body)

        assert grid[MON]["09:00"] == "off"
        assert grid[MON]["10:00"] == "open"
        assert set(grid[TUE].values()) == {"open"}
        assert body["blocks"] == []

    def test_block_outside_the_window_is_not_applied(
        self, patient_client, mock_db
    ):
        # The query already excludes non-overlapping blocks; this pins that a
        # row that slips through is still matched by date, not blanket-applied.
        wire_slots(mock_db, blocks=[make_block("2030-04-01", "2030-04-02")])

        grid = by_date(
            patient_client.get(
                f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={WED}"
            ).json()
        )

        assert set(grid[MON].values()) == {"open"}

    def test_only_overlapping_blocks_are_queried(self, patient_client, mock_db):
        wire_slots(mock_db)

        patient_client.get(
            f"/api/v1/therapists/therapist-1/slots?from_date={MON}&to_date={WED}"
        )

        _, kwargs = mock_db.availabilityblock.find_many.call_args
        assert kwargs["where"] == {
            "therapistId": "therapist-1",
            "dateFrom": {"lte": WED},
            "dateTo": {"gte": MON},
        }


BULK = "/api/v1/availability/slots/bulk"


def wire_bulk(
    mock_db,
    *,
    therapists=(),
    users=(),
    settings=(),
    rows=(),
    sessions=(),
    blocks=(),
):
    mock_db.therapist.find_many.return_value = list(therapists)
    mock_db.user.find_many.return_value = list(users)
    mock_db.setting.find_many.return_value = list(settings)
    mock_db.availabilityslot.find_many.return_value = list(rows)
    mock_db.session.find_many.return_value = list(sessions)
    mock_db.availabilityblock.find_many.return_value = list(blocks)


def entries(body):
    return {t["therapistId"]: t for t in body["therapists"]}


class TestBulkSlotsHappyPath:
    def test_two_therapists_in_one_call(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[
                make_therapist("therapist-1", "user-1"),
                make_therapist("therapist-2", "user-2"),
            ],
            users=[make_user("user-1"), make_user("user-2")],
            blocks=[make_block(MON, MON, therapist_id="therapist-2")],
        )

        response = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1,therapist-2"
            f"&from_date={MON}&to_date={TUE}"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["fromDate"] == MON
        assert body["toDate"] == TUE
        assert body["unavailable"] == []

        found = entries(body)
        # Two days of the default nine-slot grid, all open.
        assert found["therapist-1"]["openCount"] == 18
        assert found["therapist-1"]["nextFree"] == {"date": MON, "time": "09:00"}

        # therapist-2 is on approved leave on Monday, so their first free slot
        # is Tuesday — this is the bug from the single-therapist grid, and the
        # bulk read must not reintroduce it.
        assert found["therapist-2"]["openCount"] == 9
        assert found["therapist-2"]["nextFree"] == {"date": TUE, "time": "09:00"}
        assert all(s["date"] == TUE for s in found["therapist-2"]["slots"])

    def test_only_open_slots_by_default(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
            rows=[make_slot_row(MON, "09:00", "off")],
            sessions=[make_session_row(MON, "10:00")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}"
        ).json()

        slots = entries(body)["therapist-1"]["slots"]
        assert {s["status"] for s in slots} == {"open"}
        assert {s["time"] for s in slots} == set(DEFAULT_TIMES) - {"09:00", "10:00"}

    def test_no_patient_details_leak_into_a_bulk_answer(
        self, patient_client, mock_db
    ):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
            sessions=[make_session_row(MON, "10:00")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}"
            "&status=all"
        ).json()

        slots = entries(body)["therapist-1"]["slots"]
        booked = [s for s in slots if s["status"] == "booked"]
        assert len(booked) == 1
        assert set(booked[0]) == {"date", "time", "status"}
        # The patient relation is not even fetched.
        _, kwargs = mock_db.session.find_many.call_args
        assert "include" not in kwargs

    def test_status_all_returns_every_slot(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
            rows=[make_slot_row(MON, "09:00", "off")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}"
            "&status=all"
        ).json()

        slots = entries(body)["therapist-1"]["slots"]
        assert len(slots) == len(DEFAULT_TIMES)
        assert {s["status"] for s in slots} == {"open", "off"}

    def test_include_slots_false_still_answers_next_free(
        self, patient_client, mock_db
    ):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={TUE}"
            "&include_slots=false"
        ).json()

        entry = entries(body)["therapist-1"]
        assert entry["slots"] == []
        assert entry["openCount"] == 18
        assert entry["nextFree"] == {"date": MON, "time": "09:00"}

    def test_repeated_therapist_ids_parameter(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[
                make_therapist("therapist-1", "user-1"),
                make_therapist("therapist-2", "user-2"),
            ],
            users=[make_user("user-1"), make_user("user-2")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&therapist_ids=therapist-2"
            f"&from_date={MON}&to_date={MON}"
        ).json()

        assert set(entries(body)) == {"therapist-1", "therapist-2"}

    def test_duplicate_ids_are_answered_once(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1,therapist-1"
            f"&from_date={MON}&to_date={MON}"
        ).json()

        assert len(body["therapists"]) == 1

    def test_caller_order_is_preserved(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[
                # Deliberately the other way round from the query string.
                make_therapist("therapist-2", "user-2"),
                make_therapist("therapist-1", "user-1"),
            ],
            users=[make_user("user-1"), make_user("user-2")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1,therapist-2"
            f"&from_date={MON}&to_date={MON}"
        ).json()

        assert [t["therapistId"] for t in body["therapists"]] == [
            "therapist-1",
            "therapist-2",
        ]

    def test_working_hours_are_per_therapist(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[
                make_therapist("therapist-1", "user-1"),
                make_therapist("therapist-2", "user-2"),
            ],
            users=[make_user("user-1"), make_user("user-2")],
            settings=[
                SimpleNamespace(
                    key="wh_user-2",
                    jsonValue=(
                        '{"start": "14:00", "end": "16:00", "slotInterval": 60,'
                        ' "sessionDuration": 60, "breakDuration": 0,'
                        ' "daysOfWeek": ["Mon"]}'
                    ),
                )
            ],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1,therapist-2"
            f"&from_date={MON}&to_date={MON}"
        ).json()

        found = entries(body)
        assert found["therapist-1"]["openCount"] == 9
        assert [s["time"] for s in found["therapist-2"]["slots"]] == [
            "14:00",
            "15:00",
        ]

    def test_one_query_per_table_whatever_the_number_of_therapists(
        self, patient_client, mock_db
    ):
        # The whole point of the endpoint: the client's fan-out becomes a
        # fixed number of queries, not one round trip per therapist.
        wire_bulk(
            mock_db,
            therapists=[
                make_therapist(f"therapist-{n}", f"user-{n}") for n in range(1, 6)
            ],
            users=[make_user(f"user-{n}") for n in range(1, 6)],
        )
        ids = ",".join(f"therapist-{n}" for n in range(1, 6))

        response = patient_client.get(
            f"{BULK}?therapist_ids={ids}&from_date={MON}&to_date={TUE}"
        )

        assert response.status_code == 200
        assert len(response.json()["therapists"]) == 5
        assert mock_db.therapist.find_many.call_count == 1
        assert mock_db.user.find_many.call_count == 1
        assert mock_db.setting.find_many.call_count == 1
        assert mock_db.availabilityslot.find_many.call_count == 1
        assert mock_db.session.find_many.call_count == 1
        assert mock_db.availabilityblock.find_many.call_count == 1
        assert mock_db.therapist.find_unique.call_count == 0

    def test_a_bulk_read_never_writes(self, patient_client, mock_db):
        # `_get_wh` rewrites legacy working hours as a side effect. A read
        # answering for fifty therapists must not do that fifty times.
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
            settings=[
                SimpleNamespace(
                    key="wh_user-1",
                    jsonValue='{"start": "08:00", "end": "18:00", "slotInterval": 120}',
                )
            ],
        )

        patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}"
        )

        assert mock_db.setting.upsert.call_count == 0
        assert mock_db.availabilityslot.create.call_count == 0
        assert mock_db.availabilityslot.update.call_count == 0


class TestBulkSlotsEmptyAndUnanswerable:
    def test_empty_therapist_list(self, patient_client, mock_db):
        wire_bulk(mock_db)

        response = patient_client.get(f"{BULK}?from_date={MON}&to_date={MON}")

        assert response.status_code == 200
        assert response.json() == {
            "fromDate": MON,
            "toDate": MON,
            "therapists": [],
            "unavailable": [],
        }
        assert mock_db.therapist.find_many.call_count == 0

    def test_therapist_with_no_availability_at_all(self, patient_client, mock_db):
        # Every slot closed. "Asked, and they have nothing open" is a real
        # answer and must not look like a therapist we failed to check.
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
            blocks=[make_block(MON, TUE, therapist_id="therapist-1")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={TUE}"
        ).json()

        entry = entries(body)["therapist-1"]
        assert entry["slots"] == []
        assert entry["openCount"] == 0
        assert entry["nextFree"] is None
        assert body["unavailable"] == []

    def test_unknown_id_is_reported_not_fatal(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1,ghost&from_date={MON}&to_date={MON}"
        ).json()

        assert set(entries(body)) == {"therapist-1"}
        assert body["unavailable"] == [
            {"therapistId": "ghost", "reason": "not_found"}
        ]

    def test_unverified_therapist_is_hidden_like_their_profile(
        self, patient_client, mock_db
    ):
        # `GET /therapists/{id}` 404s for a therapist whose user is not
        # APPROVED. Their calendar is reported the same way, and with the same
        # reason as a missing id so nothing is disclosed about which exist.
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-9", "user-9")],
            users=[make_user("user-9", status="PENDING")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-9&from_date={MON}&to_date={MON}"
        ).json()

        assert body["therapists"] == []
        assert body["unavailable"] == [
            {"therapistId": "therapist-9", "reason": "not_found"}
        ]

    def test_info_only_therapist_is_reported_as_not_bookable(
        self, patient_client, mock_db
    ):
        wire_bulk(
            mock_db,
            therapists=[
                make_therapist("therapist-3", "user-3", listing_type="INFO_ONLY")
            ],
            users=[make_user("user-3")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-3&from_date={MON}&to_date={MON}"
        ).json()

        assert body["therapists"] == []
        assert body["unavailable"] == [
            {"therapistId": "therapist-3", "reason": "not_bookable"}
        ]

    def test_every_id_unanswerable_still_returns_200(
        self, patient_client, mock_db
    ):
        wire_bulk(mock_db, therapists=[], users=[])

        response = patient_client.get(
            f"{BULK}?therapist_ids=ghost-1,ghost-2&from_date={MON}&to_date={MON}"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["therapists"] == []
        assert [u["therapistId"] for u in body["unavailable"]] == [
            "ghost-1",
            "ghost-2",
        ]


class TestBulkSlotsNextFree:
    def test_next_free_skips_a_closed_first_slot(self, patient_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
            rows=[make_slot_row(MON, "09:00", "off")],
            sessions=[make_session_row(MON, "10:00")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}"
        ).json()

        assert entries(body)["therapist-1"]["nextFree"] == {
            "date": MON,
            "time": "11:00",
        }

    def test_next_free_is_null_for_a_window_already_gone_by(
        self, patient_client, mock_db
    ):
        # Slots in the past are still reported (the caller may be rendering a
        # past week) but they are not an answer to "when are they next free".
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
        )

        body = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1"
            "&from_date=2020-03-11&to_date=2020-03-11"
        ).json()

        entry = entries(body)["therapist-1"]
        assert entry["openCount"] == 9
        assert entry["nextFree"] is None


class TestBulkSlotsValidation:
    def test_requires_authentication(self, client):
        assert (
            client.get(f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}").status_code
            == 401
        )

    def test_any_authenticated_role_may_ask(self, therapist_client, mock_db):
        wire_bulk(
            mock_db,
            therapists=[make_therapist("therapist-1", "user-1")],
            users=[make_user("user-1")],
        )

        response = therapist_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}"
        )

        assert response.status_code == 200

    def test_too_many_ids_is_rejected(self, patient_client, mock_db):
        wire_bulk(mock_db)
        ids = ",".join(f"therapist-{n}" for n in range(60))

        response = patient_client.get(
            f"{BULK}?therapist_ids={ids}&from_date={MON}&to_date={MON}"
        )

        assert response.status_code == 400
        assert "50" in response.json()["detail"]

    def test_window_longer_than_a_month_is_rejected(self, patient_client, mock_db):
        wire_bulk(mock_db, therapists=[make_therapist("therapist-1", "user-1")])

        response = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1"
            "&from_date=2030-01-01&to_date=2030-06-30"
        )

        assert response.status_code == 400
        assert "31" in response.json()["detail"]

    def test_reversed_window_is_rejected(self, patient_client, mock_db):
        wire_bulk(mock_db, therapists=[make_therapist("therapist-1", "user-1")])

        response = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={WED}&to_date={MON}"
        )

        assert response.status_code == 400

    def test_malformed_date_is_rejected(self, patient_client, mock_db):
        wire_bulk(mock_db, therapists=[make_therapist("therapist-1", "user-1")])

        response = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date=next-tuesday&to_date={MON}"
        )

        assert response.status_code == 400

    def test_unknown_status_is_rejected(self, patient_client, mock_db):
        wire_bulk(mock_db, therapists=[make_therapist("therapist-1", "user-1")])

        response = patient_client.get(
            f"{BULK}?therapist_ids=therapist-1&from_date={MON}&to_date={MON}"
            "&status=maybe"
        )

        assert response.status_code == 400


class TestSlotsDoNotLeakPatientDetails:
    """`GET /therapists/{id}/slots` admits any authenticated user.

    A booked slot carries the patient's name and phone, so before this a
    patient could read another patient's contact details out of any
    therapist's calendar just by asking for that calendar. The owning
    therapist and an admin still need those fields to run their day.
    """

    def _booked(self, db):
        db.therapist.find_unique = AsyncMock(
            return_value=MagicMock(id="t1", userId="tu1")
        )
        return {
            "slots": [
                {
                    "date": "2026-03-10",
                    "time": "09:00",
                    "status": "booked",
                    "patientName": "Sita Rai",
                    "patientPhone": "9801234567",
                    "sessionType": "HOME_VISIT",
                    "fee": 1500.0,
                    "sessionId": "s1",
                }
            ],
            "blocks": [],
        }

    def test_a_patient_sees_the_slot_is_taken_but_not_who_took_it(
        self, patient_client, mock_db, monkeypatch
    ):
        import app.routers.therapists as r

        monkeypatch.setattr(
            r, "get_slots_for_range", AsyncMock(return_value=self._booked(mock_db))
        )
        res = patient_client.get(
            "/api/v1/therapists/t1/slots?from_date=2026-03-10&to_date=2026-03-10"
        )
        assert res.status_code == 200
        slot = res.json()["slots"][0]
        assert slot["status"] == "booked", "the slot must still read as taken"
        assert slot["patientName"] is None
        assert slot["patientPhone"] is None
        assert slot["fee"] is None
        assert slot["sessionId"] is None

    def test_another_therapist_is_no_better_placed_than_a_patient(
        self, therapist_client, mock_db, monkeypatch
    ):
        import app.routers.therapists as r

        monkeypatch.setattr(
            r, "get_slots_for_range", AsyncMock(return_value=self._booked(mock_db))
        )
        # Signed-in therapist owns a *different* therapist row.
        monkeypatch.setattr(
            r, "get_therapist_by_user", AsyncMock(return_value=MagicMock(id="other"))
        )
        res = therapist_client.get(
            "/api/v1/therapists/t1/slots?from_date=2026-03-10&to_date=2026-03-10"
        )
        assert res.json()["slots"][0]["patientPhone"] is None

    def test_the_owning_therapist_still_gets_their_day(
        self, therapist_client, mock_db, monkeypatch
    ):
        import app.routers.therapists as r

        monkeypatch.setattr(
            r, "get_slots_for_range", AsyncMock(return_value=self._booked(mock_db))
        )
        monkeypatch.setattr(
            r, "get_therapist_by_user", AsyncMock(return_value=MagicMock(id="t1"))
        )
        res = therapist_client.get(
            "/api/v1/therapists/t1/slots?from_date=2026-03-10&to_date=2026-03-10"
        )
        slot = res.json()["slots"][0]
        assert slot["patientName"] == "Sita Rai"
        assert slot["patientPhone"] == "9801234567"

    def test_an_admin_can_see_them_too(self, admin_client, mock_db, monkeypatch):
        import app.routers.therapists as r

        monkeypatch.setattr(
            r, "get_slots_for_range", AsyncMock(return_value=self._booked(mock_db))
        )
        res = admin_client.get(
            "/api/v1/therapists/t1/slots?from_date=2026-03-10&to_date=2026-03-10"
        )
        assert res.json()["slots"][0]["patientName"] == "Sita Rai"
