from prisma import Prisma


async def create_complaint(db: Prisma, data: dict):
    return await db.complaint.create(data=data)


async def get_complaints(
    db: Prisma,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    type_filter: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    complainant_id: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
):
    where: dict = {}
    if type_filter:
        where["type"] = type_filter
    if status:
        where["status"] = status
    if priority:
        where["priority"] = priority
    if category:
        where["category"] = category
    if complainant_id:
        where["complainantId"] = complainant_id
    if search:
        where["OR"] = [
            {"complainantName": {"contains": search, "mode": "insensitive"}},
            {"againstName": {"contains": search, "mode": "insensitive"}},
            {"description": {"contains": search, "mode": "insensitive"}},
        ]

    order: dict = {}
    if sort_by and sort_by in ("createdAt", "updatedAt", "priority", "status"):
        order[sort_by] = sort_order
    else:
        order["createdAt"] = "desc"

    items = await db.complaint.find_many(
        where=where, order=order, skip=skip, take=limit
    )
    total = await db.complaint.count(where=where)
    return items, total


async def get_complaint(db: Prisma, complaint_id: str):
    return await db.complaint.find_unique(
        where={"id": complaint_id},
        include={"refund": True},
    )


async def update_complaint(db: Prisma, complaint_id: str, data: dict):
    return await db.complaint.update(where={"id": complaint_id}, data=data)


async def assign_complaint(db: Prisma, complaint_id: str, assignee: str):
    return await db.complaint.update(
        where={"id": complaint_id},
        data={"assignee": assignee, "status": "Under review"},
    )


async def delete_complaint(db: Prisma, complaint_id: str):
    return await db.complaint.delete(where={"id": complaint_id})
