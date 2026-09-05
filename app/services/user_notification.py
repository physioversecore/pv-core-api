"""Per-user in-app notifications, for patients and therapists.

Separate from `notification.py`, which is the admin-wide feed: that one has no
`userId` and is addressed to whoever is on the admin dashboard, while these
rows belong to one person and drive their own notification screen.
"""
from prisma import Prisma


async def create_notification(
    db: Prisma,
    user_id: str,
    *,
    type: str,
    title: str,
    body: str,
    ref_type: str | None = None,
    ref_id: str | None = None,
):
    return await db.notification.create(
        data={
            "userId": user_id,
            "type": type,
            "title": title,
            "body": body,
            "refType": ref_type,
            "refId": ref_id,
        }
    )


async def list_notifications(db: Prisma, user_id: str, skip=0, limit=50):
    where = {"userId": user_id}
    items = await db.notification.find_many(
        where=where, skip=skip, take=limit, order={"createdAt": "desc"}
    )
    total = await db.notification.count(where=where)
    unread = await db.notification.count(where={**where, "readAt": None})
    return items, total, unread


async def mark_read(db: Prisma, user_id: str, notification_id: str):
    """Scoped by user so one account cannot mark another's notification."""
    from datetime import datetime, timezone

    found = await db.notification.find_first(
        where={"id": notification_id, "userId": user_id}
    )
    if not found:
        return None
    if found.readAt is not None:
        return found
    return await db.notification.update(
        where={"id": notification_id},
        data={"readAt": datetime.now(timezone.utc)},
    )


async def mark_all_read(db: Prisma, user_id: str) -> int:
    from datetime import datetime, timezone

    result = await db.notification.update_many(
        where={"userId": user_id, "readAt": None},
        data={"readAt": datetime.now(timezone.utc)},
    )
    return result
