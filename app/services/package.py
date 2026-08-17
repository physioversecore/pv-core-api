from prisma import Prisma


async def get_packages(
    db: Prisma,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
) -> tuple[list, int]:
    where: dict = {}
    if active_only:
        where["isActive"] = True

    packages = await db.package.find_many(
        where=where, skip=skip, take=limit, order={"sortOrder": "asc"}
    )
    total = await db.package.count(where=where)
    return packages, total


async def get_package(db: Prisma, package_id: str):
    return await db.package.find_unique(where={"id": package_id})


async def create_package(db: Prisma, data: dict):
    return await db.package.create(data=data)


async def update_package(db: Prisma, package_id: str, data: dict):
    return await db.package.update(where={"id": package_id}, data=data)


async def delete_package(db: Prisma, package_id: str):
    await db.package.delete(where={"id": package_id})
