"""Admin management of listing and coverage.

These fields were readable long before anything could set them, which left
the coverage map and information-only listings operable only by direct
database writes.
"""
import pytest

from app.services.admin import update_admin_therapist
from app.services.service_area import update_service_area


class FakeTable:
    def __init__(self, row=None):
        self.row = row
        self.updated = None

    async def find_unique(self, where, include=None):
        return self.row

    async def update(self, where, data):
        self.updated = data
        return self.row

    async def count(self, where=None):
        return 0

    async def find_many(self, **kwargs):
        return []


class TestTherapistListing:
    @pytest.mark.asyncio
    async def test_an_admin_can_geocode_and_link_a_clinic(self, monkeypatch):
        db, therapist = _db()

        await update_admin_therapist(
            db,
            "t1",
            {
                "latitude": 27.7,
                "longitude": 85.3,
                "serviceRadiusKm": 8,
                "clinicId": "c1",
                "listingType": "INFO_ONLY",
            },
        )

        sent = therapist.updated
        assert sent["latitude"] == 27.7
        assert sent["serviceRadiusKm"] == 8
        assert sent["clinicId"] == "c1"
        assert sent["listingType"] == "INFO_ONLY"

    @pytest.mark.asyncio
    async def test_an_unknown_listing_type_is_refused(self):
        db, therapist = _db()

        with pytest.raises(ValueError):
            await update_admin_therapist(db, "t1", {"listingType": "SOMETIMES"})

        assert therapist.updated is None

    @pytest.mark.asyncio
    async def test_untouched_fields_are_left_alone(self):
        # exclude_none on the router means a partial edit must not blank the
        # coordinates someone set earlier.
        db, therapist = _db()

        await update_admin_therapist(db, "t1", {"specialty": "Neuro"})

        assert therapist.updated == {"specialty": "Neuro"}


class TestServiceAreaCoordinates:
    @pytest.mark.asyncio
    async def test_an_area_can_be_geocoded(self):
        area = FakeTable(_area())
        db = type("Db", (), {"servicearea": area, "therapistservicearea": FakeTable(), "session": FakeTable()})()

        await update_service_area(db, "a1", {"latitude": 27.68, "longitude": 85.34})

        assert area.updated["latitude"] == 27.68
        assert area.updated["longitude"] == 85.34


def _area():
    return type("A", (), {
        "id": "a1", "name": "Baneshwor", "localities": [],
        "status": "Active", "latitude": None, "longitude": None,
        "therapistServiceAreas": [],
    })()


def _db():
    from datetime import datetime

    therapist_row = type("T", (), {
        "id": "t1", "userId": "u1", "name": "Dr. Test", "city": "Lalitpur",
        "specialty": "Sports", "rating": 4.5, "gender": "M", "price": 1500.0,
        "experience": 5, "bio": "", "mediaUrls": None, "listingType": "BOOKABLE",
        "clinicId": None, "clinic": None, "latitude": None, "longitude": None,
        "serviceRadiusKm": None,
    })()
    user_row = type("U", (), {
        "id": "u1", "name": "Dr. Test", "email": "t@test.com", "phone": "",
        "role": "THERAPIST", "status": "APPROVED", "city": "Lalitpur",
        "specialty": "Sports", "createdAt": datetime(2026, 1, 1),
    })()

    therapist = FakeTable(therapist_row)
    db = type("Db", (), {
        "therapist": therapist,
        "user": FakeTable(user_row),
        "verification": FakeTable(),
        "session": FakeTable(),
        "clinic": FakeTable(),
    })()
    return db, therapist
