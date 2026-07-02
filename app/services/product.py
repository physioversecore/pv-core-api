from prisma import Prisma


async def get_products(db: Prisma, category: str | None = None, skip=0, limit=100):
    where = {}
    if category:
        where["category"] = category.upper()
    products = await db.product.find_many(
        where=where, skip=skip, take=limit, order={"createdAt": "desc"}
    )
    total = await db.product.count(where=where)
    return products, total


async def get_product(db: Prisma, product_id: str):
    return await db.product.find_unique(where={"id": product_id})


async def create_product(db: Prisma, data: dict):
    return await db.product.create(data=data)


async def update_product(db: Prisma, product_id: str, data: dict):
    return await db.product.update(where={"id": product_id}, data=data)


async def delete_product(db: Prisma, product_id: str):
    await db.product.delete(where={"id": product_id})
