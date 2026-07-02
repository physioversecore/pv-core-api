from prisma import Prisma


async def create_payment(db: Prisma, data: dict):
    return await db.payment.create(data=data)


async def get_payments_for_user(db: Prisma, user_id: str, skip=0, limit=100):
    payments = await db.payment.find_many(
        where={"userId": user_id},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )
    total = await db.payment.count(where={"userId": user_id})
    return payments, total


async def get_all_payments(db: Prisma, skip=0, limit=100):
    payments = await db.payment.find_many(
        skip=skip, take=limit, order={"createdAt": "desc"}
    )
    total = await db.payment.count()
    return payments, total


async def get_payment(db: Prisma, payment_id: str):
    return await db.payment.find_unique(where={"id": payment_id})


async def update_payment(db: Prisma, payment_id: str, data: dict):
    return await db.payment.update(where={"id": payment_id}, data=data)
