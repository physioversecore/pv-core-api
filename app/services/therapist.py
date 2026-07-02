from prisma import Prisma


async def get_therapists(db: Prisma, skip: int = 0, limit: int = 100):
    therapists = await db.therapist.find_many(
        skip=skip, take=limit, order={"createdAt": "desc"}
    )
    total = await db.therapist.count()
    return therapists, total


async def get_therapist(db: Prisma, therapist_id: str):
    return await db.therapist.find_unique(where={"id": therapist_id})


async def get_therapist_by_user(db: Prisma, user_id: str):
    return await db.therapist.find_unique(where={"userId": user_id})


async def create_therapist(db: Prisma, user_id: str, data: dict):
    return await db.therapist.create(data={"userId": user_id, **data})


async def update_therapist(db: Prisma, therapist_id: str, data: dict):
    return await db.therapist.update(where={"id": therapist_id}, data=data)


async def delete_therapist(db: Prisma, therapist_id: str):
    await db.therapist.delete(where={"id": therapist_id})
