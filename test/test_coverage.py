"""Service-area coverage.

The interesting rules are what happens when data is missing: most therapists
are not geocoded yet, and coverage must degrade to something honest rather
than claiming everyone is out of range.
"""
import pytest

from app.services.coverage import haversine_km, therapists_covering


class TestDistance:
    def test_measures_a_known_separation(self):
        # Kathmandu to Pokhara is roughly 200 km apart.
        km = haversine_km(27.7172, 85.3240, 28.2096, 83.9856)
        assert 130 < km < 230

    def test_the_same_point_is_zero(self):
        assert haversine_km(27.7, 85.3, 27.7, 85.3) == pytest.approx(0, abs=0.001)

    def test_a_missing_coordinate_gives_no_distance(self):
        # Rather than defaulting to 0, which would read as "right here".
        assert haversine_km(None, 85.3, 27.7, 85.3) is None
        assert haversine_km(27.7, 85.3, 27.7, None) is None


class FakeTable:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def find_many(self, where=None, include=None, order=None):
        return list(self.rows)

    async def find_unique(self, where):
        for row in self.rows:
            if getattr(row, "id", None) == where.get("id"):
                return row
        return None


class FakeDb:
    def __init__(self, areas, therapists, links):
        self.servicearea = FakeTable(areas)
        self.therapist = FakeTable(therapists)
        self.therapistservicearea = FakeTable(links)


def area(id="a1", lat=27.6796, lon=85.3169):
    return type("Area", (), {"id": id, "name": "Jhamsikhel", "latitude": lat, "longitude": lon})()


def therapist(id, *, lat=None, lon=None, radius=None, name="T"):
    return type("Therapist", (), {
        "id": id, "name": name, "specialty": "Sports", "city": "Lalitpur",
        "price": 1500.0, "listingType": "BOOKABLE", "clinic": None,
        "latitude": lat, "longitude": lon, "serviceRadiusKm": radius,
    })()


def link(therapist_id, area_id="a1"):
    return type("Link", (), {"therapistId": therapist_id, "serviceAreaId": area_id})()


class TestCoverage:
    @pytest.mark.asyncio
    async def test_radius_decides_when_both_sides_are_geocoded(self):
        near = therapist("near", lat=27.6800, lon=85.3170, radius=6)
        far = therapist("far", lat=28.2096, lon=83.9856, radius=6)
        db = FakeDb([area()], [near, far], [])

        rows, _ = await therapists_covering(db, "a1")
        by_id = {t.id: covers for t, covers, _ in rows}

        assert by_id["near"] is True
        assert by_id["far"] is False

    @pytest.mark.asyncio
    async def test_an_explicit_link_covers_without_any_coordinates(self):
        # The admin-managed link is authoritative, and most therapists are not
        # geocoded yet -- without this they would all read as out of range.
        plain = therapist("t1")
        db = FakeDb([area()], [plain], [link("t1")])

        rows, _ = await therapists_covering(db, "a1")

        assert rows[0][1] is True

    @pytest.mark.asyncio
    async def test_an_explicit_link_wins_over_distance(self):
        # Coverage is a business decision, not only a radius.
        distant = therapist("t1", lat=28.2096, lon=83.9856, radius=1)
        db = FakeDb([area()], [distant], [link("t1")])

        rows, _ = await therapists_covering(db, "a1")

        assert rows[0][1] is True

    @pytest.mark.asyncio
    async def test_out_of_range_therapists_are_still_returned(self):
        # The design greys them rather than hiding them, so the map is never
        # mysteriously empty.
        far = therapist("far", lat=28.2096, lon=83.9856, radius=1)
        db = FakeDb([area()], [far], [])

        rows, _ = await therapists_covering(db, "a1")

        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_covering_therapists_sort_first(self):
        far = therapist("far", lat=28.2096, lon=83.9856, radius=1, name="A far")
        near = therapist("near", lat=27.6800, lon=85.3170, radius=6, name="Z near")
        db = FakeDb([area()], [far, near], [])

        rows, _ = await therapists_covering(db, "a1")

        assert rows[0][0].id == "near", "covering first, regardless of name"

    @pytest.mark.asyncio
    async def test_no_area_returns_everyone_uncovered(self):
        db = FakeDb([], [therapist("t1"), therapist("t2")], [])

        rows, chosen = await therapists_covering(db, None)

        assert chosen is None
        assert len(rows) == 2
        assert all(not covers for _, covers, _ in rows)
