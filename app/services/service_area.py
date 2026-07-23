from datetime import datetime, timezone

from prisma import Json, Prisma


def _derive_status(assigned_therapists: int) -> str:
    return "Active" if assigned_therapists >= 2 else "Low coverage"


async def get_service_areas(
    db: Prisma,
    *,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
):
    where: dict = {}

    if search:
        where["name"] = {"contains": search, "mode": "insensitive"}

    if status:
        where["status"] = status

    order: dict = {"createdAt": "desc"}
    if sort_by == "name":
        order = {"name": sort_order}

    total = await db.servicearea.count(where=where)

    areas = await db.servicearea.find_many(
        where=where,
        skip=skip,
        take=limit,
        order=order,
        include={"therapistServiceAreas": True},
    )

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    items = []
    for area in areas:
        assigned_count = len(area.therapistServiceAreas)

        therapist_ids = [tsa.therapistId for tsa in area.therapistServiceAreas]
        bookings_count = 0
        if therapist_ids:
            bookings_count = await db.session.count(
                where={
                    "therapistId": {"in": therapist_ids},
                    "date": {"gte": month_start.replace(tzinfo=None)},
                }
            )

        items.append({
            "id": area.id,
            "name": area.name,
            "localities": area.localities if isinstance(area.localities, list) else [],
            "assignedTherapists": assigned_count,
            "bookingsThisMonth": bookings_count,
            "status": area.status,
        })

    return items, total


async def get_service_area(db: Prisma, area_id: str):
    area = await db.servicearea.find_unique(
        where={"id": area_id},
        include={"therapistServiceAreas": True},
    )
    if not area:
        return None

    assigned_count = len(area.therapistServiceAreas)
    therapist_ids = [tsa.therapistId for tsa in area.therapistServiceAreas]

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    bookings_count = 0
    if therapist_ids:
        bookings_count = await db.session.count(
            where={
                "therapistId": {"in": therapist_ids},
                "date": {"gte": month_start.replace(tzinfo=None)},
            }
        )

    return {
        "id": area.id,
        "name": area.name,
        "localities": area.localities if isinstance(area.localities, list) else [],
        "assignedTherapists": assigned_count,
        "bookingsThisMonth": bookings_count,
        "status": area.status,
    }


async def create_service_area(db: Prisma, data: dict):
    localities = data.get("localities", []) or []
    therapist_ids = data.get("therapistIds") or []

    area = await db.servicearea.create(
        data={
            "name": data["name"],
            "localities": Json(localities),
            "status": _derive_status(len(therapist_ids)),
        }
    )

    if therapist_ids:
        for tid in therapist_ids:
            therapist = await db.therapist.find_unique(where={"id": tid})
            if therapist:
                await db.therapistservicearea.create(
                    data={"therapistId": tid, "serviceAreaId": area.id}
                )

    return await get_service_area(db, area.id)


async def update_service_area(db: Prisma, area_id: str, data: dict):
    area = await db.servicearea.find_unique(where={"id": area_id})
    if not area:
        return None

    update_data: dict = {}
    if "name" in data and data["name"] is not None:
        update_data["name"] = data["name"]
    if "localities" in data and data["localities"] is not None:
        update_data["localities"] = Json(data["localities"])

    if update_data:
        await db.servicearea.update(where={"id": area_id}, data=update_data)

    return await get_service_area(db, area_id)


async def delete_service_area(db: Prisma, area_id: str):
    area = await db.servicearea.find_unique(where={"id": area_id})
    if not area:
        return False
    await db.servicearea.delete(where={"id": area_id})
    return True


async def assign_therapist_to_area(db: Prisma, area_id: str, therapist_id: str):
    area = await db.servicearea.find_unique(where={"id": area_id})
    if not area:
        return None

    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    if not therapist:
        return None

    existing = await db.therapistservicearea.find_unique(
        where={"therapistId_serviceAreaId": {"therapistId": therapist_id, "serviceAreaId": area_id}}
    )
    if existing:
        return await get_service_area(db, area_id)

    await db.therapistservicearea.create(
        data={"therapistId": therapist_id, "serviceAreaId": area_id}
    )

    updated_area = await db.servicearea.find_unique(
        where={"id": area_id},
        include={"therapistServiceAreas": True},
    )
    assigned_count = len(updated_area.therapistServiceAreas)
    await db.servicearea.update(
        where={"id": area_id},
        data={"status": _derive_status(assigned_count)},
    )

    return await get_service_area(db, area_id)
