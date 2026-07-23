from datetime import datetime, timezone
from prisma import Prisma


async def log_admin_activity(
    db: Prisma,
    admin_id: str,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict | None = None,
):
    await db.activitylog.create(
        data={
            "adminId": admin_id,
            "action": action,
            "targetType": target_type,
            "targetId": target_id,
            "metadata": metadata or {},
            "createdAt": datetime.now(timezone.utc),
        }
    )


async def get_activity_logs(
    db: Prisma,
    skip: int = 0,
    limit: int = 50,
    admin_id: str | None = None,
    target_type: str | None = None,
    action_type: str | None = None,
):
    where: dict = {}
    if admin_id:
        where["adminId"] = admin_id
    if target_type:
        where["targetType"] = target_type
    if action_type:
        where["action"] = action_type

    items = await db.activitylog.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )
    total = await db.activitylog.count(where=where)
    return items, total
