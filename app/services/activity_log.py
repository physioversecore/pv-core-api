from datetime import datetime, time, timezone
from prisma import Json, Prisma


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
            "metadata": Json(metadata) if metadata else Json({}),
            "createdAt": datetime.now(timezone.utc),
        }
    )


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def build_activity_description(action: str, target_type: str, target_id: str, metadata: dict) -> str:
    meta = metadata or {}

    if meta.get("name"):
        subject = meta["name"]
    else:
        subject = f"{target_type} {target_id}"

    detail = ""
    if meta.get("status") is not None:
        detail = f" — status: {meta['status']}"
    elif meta.get("note"):
        detail = f" — {meta['note']}"
    elif meta.get("amount") is not None:
        detail = f" — amount: {meta['amount']}"
    elif meta.get("assigneeId"):
        detail = f" — assigned to {meta['assigneeId']}"
    elif meta.get("reason"):
        detail = f" — reason: {meta['reason']}"

    return f"{humanize_action(action)} — {subject}{detail}"


ACTIONS = [
    (("APPROVE_THERAPIST",), "Therapist verified", "approve"),
    (("REJECT_THERAPIST",), "Therapist rejected", "reject"),
    (("TOGGLE_USER_STATUS",), "User status updated", "update"),
    (("CREATE_THERAPIST",), "Therapist created", "create"),
    (("UPDATE_THERAPIST",), "Therapist updated", "update"),
    (("DELETE_THERAPIST",), "Therapist removed", "delete"),
    (("UPDATE_PATIENT",), "Patient updated", "update"),
    (("DELETE_PATIENT",), "Patient removed", "delete"),
    (("APPROVE_VERIFICATION",), "Verification approved", "approve"),
    (("REJECT_VERIFICATION",), "Verification rejected", "reject"),
    (("SUSPEND_VERIFICATION",), "Verification suspended", "suspend"),
    (("UPDATE_COMPLAINT",), "Complaint updated", "update"),
    (("ASSIGN_COMPLAINT",), "Complaint assigned", "assign"),
    (("DELETE_COMPLAINT",), "Complaint removed", "delete"),
    (("CREATE_REFUND",), "Refund created", "create"),
    (("UPDATE_REFUND",), "Refund updated", "update"),
    (("ASSIGN_REFUND",), "Refund assigned", "assign"),
    (("DELETE_REFUND",), "Refund removed", "delete"),
    (("APPROVE_LEAVE",), "Leave approved", "approve"),
    (("REJECT_LEAVE",), "Leave rejected", "reject"),
    (("UPDATE_PAYMENT",), "Payment updated", "update"),
    (("UPDATE_SERVICE_AREA",), "Service area updated", "update"),
    (("UPDATE_SETTING",), "Setting updated", "update"),
    (("UPDATE_TEAM",), "Team member updated", "update"),
    (("INVITE_TEAM",), "Team member invited", "create"),
    (("CREATE_PRODUCT",), "Product created", "create"),
    (("UPDATE_PRODUCT",), "Product updated", "update"),
    (("DELETE_PRODUCT",), "Product removed", "delete"),
    (("SCHEDULE_REVIEW",), "Performance review scheduled", "create"),
    (("RESOLVE_REVIEW",), "Performance review resolved", "resolve"),
    (("UPDATE_PAYOUT",), "Payout updated", "update"),
]


def humanize_action(action: str) -> str:
    for codes, label, _ in ACTIONS:
        if action in codes:
            return label
    return action.replace("_", " ").title()


async def get_activity_logs(
    db: Prisma,
    skip: int = 0,
    limit: int = 50,
    admin_id: str | None = None,
    target_type: str | None = None,
    action_type: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    where: dict = {}
    if admin_id:
        where["adminId"] = admin_id
    if target_type:
        where["targetType"] = target_type
    if action_type:
        where["action"] = action_type

    if date_from:
        d = parse_date(date_from)
        if d:
            where.setdefault("createdAt", {})
            where["createdAt"]["gte"] = d.replace(tzinfo=timezone.utc)
    if date_to:
        d = parse_date(date_to)
        if d:
            where.setdefault("createdAt", {})
            where["createdAt"]["lte"] = datetime.combine(d.date(), time.max, tzinfo=timezone.utc)

    if search and search.strip():
        where["OR"] = [
            {"action": {"contains": search, "mode": "insensitive"}},
            {"targetType": {"contains": search, "mode": "insensitive"}},
            {"targetId": {"contains": search, "mode": "insensitive"}},
            {"metadata": {"path": ["name"], "string_contains": search}},
        ]

    items = await db.activitylog.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
        include={"admin": True},
    )
    total = await db.activitylog.count(where=where)

    entries = []
    for i in items:
        admin = i.admin
        metadata = i.metadata or {}
        entries.append({
            "id": i.id,
            "timestamp": i.createdAt.isoformat() if i.createdAt else "",
            "actor": admin.name if admin else "System",
            "actorId": i.adminId,
            "actionType": humanize_action(i.action),
            "description": build_activity_description(i.action, i.targetType, i.targetId, metadata),
        })
    return entries, total
