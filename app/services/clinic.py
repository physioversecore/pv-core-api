from prisma import Prisma


async def get_clinics(
    db: Prisma,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    city: str | None = None,
) -> tuple[list, int]:
    where: dict = {}
    if search:
        where["OR"] = [
            {"name": {"contains": search, "mode": "insensitive"}},
            {"area": {"contains": search, "mode": "insensitive"}},
            {"address": {"contains": search, "mode": "insensitive"}},
        ]
    if city:
        where["city"] = {"contains": city, "mode": "insensitive"}

    clinics = await db.clinic.find_many(where=where, skip=skip, take=limit, order={"createdAt": "desc"})
    total = await db.clinic.count(where=where)
    return clinics, total


async def get_clinic(db: Prisma, clinic_id: str):
    return await db.clinic.find_unique(where={"id": clinic_id})


async def create_clinic(db: Prisma, data: dict):
    return await db.clinic.create(data=data)


async def update_clinic(db: Prisma, clinic_id: str, data: dict):
    return await db.clinic.update(where={"id": clinic_id}, data=data)


async def delete_clinic(db: Prisma, clinic_id: str):
    await db.clinic.delete(where={"id": clinic_id})
