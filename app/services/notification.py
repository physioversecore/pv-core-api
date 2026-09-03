from datetime import datetime, timezone

from prisma import Prisma


ACTION_MAP = {
    "booking": ("View booking", "/admin/bookings", "booking"),
    "reschedule": ("View schedule", "/admin/bookings", "booking"),
    "complaint": ("Review complaint", "/admin/complaints", "complaint"),
    "payment": ("View payments", "/admin/payments", "payment"),
    "refund": ("View refunds", "/admin/refunds", "refund"),
    "leave": ("View leaves", "/admin/leave", "leave"),
    "verification": ("Review application", "/admin/verification", "verification"),
    "therapist": ("Review therapist", "/admin/therapists", "therapist"),
    "system": (None, None, None),
}


async def log_admin_notification(
    db: Prisma,
    *,
    category: str,
    message: str,
    action_type: str | None = None,
    action_id: str | None = None,
) -> None:
    """Create an admin notification. Fire-and-forget safe — catches and logs errors."""
    try:
        await db.adminnotification.create(
            data={
                "category": category,
                "message": message,
                "read": False,
                "actionType": action_type,
                "actionId": action_id,
                "relatedEntityType": ACTION_MAP.get(category, (None, None, None))[2],
                "relatedEntityId": action_id,
                "createdAt": datetime.now(timezone.utc),
            }
        )
    except Exception:
        pass


def _build_response(n) -> dict:
    action_label, action_href, _ = ACTION_MAP.get(
        n.category, (None, None, None)
    )
    return {
        "id": n.id,
        "category": n.category,
        "message": n.message,
        "timestamp": n.createdAt.isoformat() if n.createdAt else "",
        "read": n.read,
        "actionLabel": action_label,
        "actionHref": action_href,
        "relatedEntityType": n.relatedEntityType,
        "relatedEntityId": n.relatedEntityId,
    }


async def list_admin_notifications(
    db: Prisma,
    *,
    skip: int = 0,
    limit: int = 20,
    category: str | None = None,
    read: bool | None = None,
) -> tuple[list[dict], int, int]:
    """Return (items, total, unread_count)."""
    where: dict = {}
    if category:
        where["category"] = category
    if read is not None:
        where["read"] = read

    total = await db.adminnotification.count(where=where)
    unread_count = await db.adminnotification.count(where={"read": False})

    items = await db.adminnotification.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )
    return [_build_response(n) for n in items], total, unread_count


async def mark_notification_read(db: Prisma, notification_id: str) -> dict | None:
    n = await db.adminnotification.find_unique(where={"id": notification_id})
    if not n:
        return None
    updated = await db.adminnotification.update(
        where={"id": notification_id},
        data={"read": True, "readAt": datetime.now(timezone.utc)},
    )
    return _build_response(updated)


async def mark_all_notifications_read(db: Prisma) -> int:
    unread = await db.adminnotification.count(where={"read": False})
    await db.adminnotification.update_many(
        where={"read": False},
        data={"read": True, "readAt": datetime.now(timezone.utc)},
    )
    return unread
