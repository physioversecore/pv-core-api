"""Service-area coverage for the map screen.

Answers one question: from a named area, which therapists and clinics can
actually reach you. Two independent signals decide it, and either is enough:

* an explicit admin-managed link in TherapistServiceArea, which is the
  authoritative answer, and
* distance, when both the area and the therapist have been geocoded.

Distance alone would be wrong on its own -- coverage is a business decision,
not only a radius -- and the explicit link alone would leave newly added
areas uncovered until someone maintains them.
"""
from math import asin, cos, radians, sin, sqrt

from prisma import Prisma

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2) -> float | None:
    """Great-circle distance, or None if either point is missing."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


async def list_service_areas(db: Prisma):
    return await db.servicearea.find_many(
        where={"status": "Active"}, order={"name": "asc"}
    )


async def therapists_covering(db: Prisma, area_id: str | None):
    """Therapists ranked with the ones covering the area first.

    Returns (therapist, covers, distance_km) tuples. Everyone is returned, not
    only those in range: the design shows out-of-range therapists greyed
    rather than hiding them, so the map does not look empty.
    """
    area = None
    if area_id:
        area = await db.servicearea.find_unique(where={"id": area_id})

    therapists = await db.therapist.find_many(
        where={"user": {"status": "APPROVED"}}, include={"clinic": True}
    )

    linked_ids = set()
    if area:
        links = await db.therapistservicearea.find_many(
            where={"serviceAreaId": area.id}
        )
        linked_ids = {link.therapistId for link in links}

    results = []
    for therapist in therapists:
        distance = None
        covers = therapist.id in linked_ids

        if area is not None:
            distance = haversine_km(
                area.latitude, area.longitude,
                therapist.latitude, therapist.longitude,
            )
            radius = therapist.serviceRadiusKm
            if not covers and distance is not None and radius:
                covers = distance <= radius

        results.append((therapist, covers, distance))

    # Covering first, then nearest, then a stable name order so the list does
    # not reshuffle between identical requests.
    results.sort(
        key=lambda row: (
            not row[1],
            row[2] if row[2] is not None else float("inf"),
            row[0].name or "",
        )
    )
    return results, area


async def clinics_in_area(db: Prisma, area_id: str | None):
    """Clinics ordered by distance from the area, nearest first."""
    area = None
    if area_id:
        area = await db.servicearea.find_unique(where={"id": area_id})

    clinics = await db.clinic.find_many()
    rows = []
    for clinic in clinics:
        distance = (
            haversine_km(area.latitude, area.longitude, clinic.latitude, clinic.longitude)
            if area is not None
            else None
        )
        rows.append((clinic, distance))

    rows.sort(key=lambda r: r[1] if r[1] is not None else float("inf"))
    return rows, area
