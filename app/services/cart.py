from prisma import Prisma


async def get_cart(db: Prisma, user_id: str):
    items = await db.cartitem.find_many(
        where={"userId": user_id},
        include={"product": True},
        order={"createdAt": "asc"},
    )
    return items


async def add_to_cart(db: Prisma, user_id: str, data: dict):
    existing = await db.cartitem.find_first(
        where={
            "userId": user_id,
            "productId": data["productId"],
            "type": data.get("type", "BUY"),
        }
    )
    if existing:
        return await db.cartitem.update(
            where={"id": existing.id},
            data={"quantity": existing.quantity + data.get("quantity", 1)},
        )
    return await db.cartitem.create(
        data={
            "userId": user_id,
            "productId": data["productId"],
            "type": data.get("type", "BUY"),
            "quantity": data.get("quantity", 1),
            "rentalDays": data.get("rentalDays", 7),
        }
    )


async def update_cart_item(db: Prisma, item_id: str, data: dict):
    return await db.cartitem.update(where={"id": item_id}, data=data)


async def remove_cart_item(db: Prisma, item_id: str):
    await db.cartitem.delete(where={"id": item_id})


async def clear_cart(db: Prisma, user_id: str):
    await db.cartitem.delete_many(where={"userId": user_id})
