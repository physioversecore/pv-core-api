from datetime import datetime, timezone
from prisma import Prisma
from fastapi import HTTPException


REASON_MAP = {
    "No-show": "NO_SHOW",
    "Double charge": "DOUBLE_CHARGE",
    "Service quality": "SERVICE_QUALITY",
    "Cancellation": "CANCELLATION",
}

REASON_REVERSE = {v: k for k, v in REASON_MAP.items()}

STATUS_MAP = {
    "Pending": "PENDING",
    "Approved": "APPROVED",
    "Denied": "DENIED",
}

STATUS_REVERSE = {v: k for k, v in STATUS_MAP.items()}


def _build_refund_response(r) -> dict:
    return {
        "id": r.id,
        "patientId": r.patientId,
        "patient": r.patient.name if r.patient else "",
        "bookingId": r.bookingId,
        "amount": r.amount,
        "reason": REASON_REVERSE.get(r.reason, r.reason),
        "status": STATUS_REVERSE.get(r.status, r.status),
        "denyReason": r.denyReason,
        "resolvedAt": r.resolvedAt,
        "filed": r.createdAt.strftime("%Y-%m-%d") if r.createdAt else "",
        "assigneeId": getattr(r, "assigneeId", None),
        "source": getattr(r, "source", None),
        "complaintId": getattr(r, "complaintId", None),
        "notes": getattr(r, "notes", None),
    }


async def get_refunds(
    db: Prisma,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    reason: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
):
    where: dict = {}
    if reason:
        where["reason"] = REASON_MAP.get(reason, reason)
    if status:
        where["status"] = STATUS_MAP.get(status, status)
    if date_from:
        try:
            where["createdAt"] = {"gte": datetime.fromisoformat(date_from)}
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            if "createdAt" in where:
                where["createdAt"]["lte"] = dt_to
            else:
                where["createdAt"] = {"lte": dt_to}
        except (ValueError, TypeError):
            pass
    if search:
        where["OR"] = [
            {"patient": {"name": {"contains": search, "mode": "insensitive"}}},
            {"bookingId": {"contains": search, "mode": "insensitive"}},
        ]

    order: dict = {}
    if sort_by and sort_by in ("amount", "reason", "status", "filed", "createdAt", "patient"):
        if sort_by == "patient":
            order["patient"] = {"name": sort_order}
        elif sort_by == "filed":
            order["createdAt"] = sort_order
        else:
            order[sort_by] = sort_order
    else:
        order["createdAt"] = "desc"

    items = await db.refund.find_many(
        where=where,
        order=order,
        skip=skip,
        take=limit,
        include={"patient": True},
    )
    total = await db.refund.count(where=where)
    return [_build_refund_response(r) for r in items], total


async def create_refund(db: Prisma, data: dict):
    data["reason"] = REASON_MAP.get(data["reason"], data["reason"])
    if "status" in data and data["status"]:
        data["status"] = STATUS_MAP.get(data["status"], data["status"])
    else:
        data["status"] = "PENDING"

    refund = await db.refund.create(
        data=data,
        include={"patient": True},
    )
    return _build_refund_response(refund)


async def get_refund(db: Prisma, refund_id: str):
    r = await db.refund.find_unique(
        where={"id": refund_id},
        include={"patient": True, "complaint": True},
    )
    if not r:
        return None
    resp = _build_refund_response(r)
    if r.complaint:
        resp["complaintId"] = r.complaint.id
    return resp


async def update_refund(db: Prisma, refund_id: str, data: dict):
    if "reason" in data and data["reason"]:
        data["reason"] = REASON_MAP.get(data["reason"], data["reason"])
    if "status" in data and data["status"]:
        data["status"] = STATUS_MAP.get(data["status"], data["status"])
        if data["status"] in ("APPROVED", "DENIED") and "resolvedAt" not in data:
            data["resolvedAt"] = datetime.now(timezone.utc)

    updated = await db.refund.update(
        where={"id": refund_id},
        data=data,
        include={"patient": True},
    )
    return _build_refund_response(updated)


async def delete_refund(db: Prisma, refund_id: str):
    await db.refund.delete(where={"id": refund_id})


async def assign_refund(db: Prisma, refund_id: str, assignee_id: str):
    updated = await db.refund.update(
        where={"id": refund_id},
        data={"assigneeId": assignee_id},
        include={"patient": True},
    )
    return _build_refund_response(updated)


async def create_manual_case(db: Prisma, payload: dict, admin_id: str):
    if payload.get("alsoCreateDispute"):
        desc = payload.get("disputeDescription", "")
        if not desc or len(desc) < 20:
            raise HTTPException(422, "disputeDescription must be at least 20 characters")
        if not payload.get("disputeCategory"):
            raise HTTPException(422, "disputeCategory is required when alsoCreateDispute is true")

    complaint = None
    refund = None

    async with db.tx() as tx:
        if payload.get("alsoCreateDispute"):
            complaint = await tx.complaint.create(
                data={
                    "type": "billing_dispute",
                    "complainantId": payload["patientId"],
                    "complainantName": await _resolve_name(tx, payload["patientId"]),
                    "againstId": "N/A",
                    "againstName": "N/A",
                    "category": payload["disputeCategory"],
                    "priority": payload.get("disputePriority", "Normal"),
                    "status": "Open",
                    "description": payload["disputeDescription"],
                    "bookingId": payload["bookingId"],
                    "preferredOutcome": "Refund",
                    "assignee": payload.get("assigneeId"),
                    "source": "ADMIN_MANUAL",
                    "adminNotes": payload.get("notes"),
                }
            )

        refund = await tx.refund.create(
            data={
                "patientId": payload["patientId"],
                "bookingId": payload["bookingId"],
                "amount": payload["amount"],
                "reason": REASON_MAP.get(payload["reason"], payload["reason"]),
                "status": "PENDING",
                "assigneeId": payload.get("assigneeId"),
                "source": "ADMIN_MANUAL",
                "notes": payload.get("notes"),
                "complaintId": complaint.id if complaint else None,
            },
            include={"patient": True},
        )

        if complaint:
            await tx.complaint.update(
                where={"id": complaint.id}, data={"refundId": refund.id}
            )

    from app.services.activity_log import log_admin_activity
    await log_admin_activity(
        db=db,
        admin_id=admin_id,
        action="CREATE_MANUAL_REFUND_CASE",
        target_type="Refund",
        target_id=refund.id,
        metadata={
            "linkedComplaintId": complaint.id if complaint else None,
            "source": "ADMIN_MANUAL",
            "amount": payload["amount"],
        },
    )

    refund_resp = _build_refund_response(refund)
    complaint_resp = None
    if complaint:
        complaint_resp = {
            "id": complaint.id,
            "type": complaint.type,
            "status": complaint.status,
            "category": complaint.category,
        }

    return {"refund": refund_resp, "complaint": complaint_resp}


async def _resolve_name(db: Prisma, user_id: str) -> str:
    user = await db.user.find_unique(where={"id": user_id})
    return user.name if user else "Unknown"


async def get_refund_stats(db: Prisma):
    pending = await db.refund.count(where={"status": "PENDING"})

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    refunded_this_month = await db.refund.count(
        where={"status": "APPROVED", "createdAt": {"gte": month_start}}
    )

    total_refunds = await db.refund.count()
    denied = await db.refund.count(where={"status": "DENIED"})
    dispute_rate = round((denied / total_refunds * 100) if total_refunds > 0 else 0.0, 1)

    resolved = await db.refund.find_many(
        where={"status": {"in": ["APPROVED", "DENIED"]}, "resolvedAt": {"not": None}},
        include={"patient": True},
    )
    if resolved:
        total_days = sum(
            (r.resolvedAt - r.createdAt).days for r in resolved if r.resolvedAt
        )
        avg_days = round(total_days / len(resolved), 1)
    else:
        avg_days = 0.0

    return {
        "pending": pending,
        "refundedThisMonth": refunded_this_month,
        "disputeRate": dispute_rate,
        "avgResolutionDays": avg_days,
    }
