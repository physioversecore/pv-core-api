from prisma import Prisma


async def get_services(
    db: Prisma,
    category: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list, int]:
    where = {"isActive": True}
    if category:
        where["category"] = category

    services = await db.service.find_many(
        where=where,
        order={"sortOrder": "asc"},
        skip=skip,
        take=limit,
    )
    total = await db.service.count(where=where)
    return services, total


async def get_service(db: Prisma, service_id: str):
    return await db.service.find_unique(where={"id": service_id})


async def create_service(db: Prisma, data: dict):
    return await db.service.create(data=data)


async def update_service(db: Prisma, service_id: str, data: dict):
    return await db.service.update(where={"id": service_id}, data=data)


async def delete_service(db: Prisma, service_id: str):
    await db.service.delete(where={"id": service_id})
