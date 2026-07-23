from datetime import datetime
from prisma import Prisma


def _build_verification_response(v):
    return {
        "id": v.id,
        "therapistId": v.therapistId,
        "therapist": v.therapist.name if v.therapist else "",
        "documentType": v.documentType,
        "uploaded": v.uploaded,
        "expires": v.expires,
        "status": v.status,
        "severity": v.severity,
        "reportedBy": v.reportedBy,
        "phone": v.phone if v.phone else (v.therapist.user.phone if v.therapist and v.therapist.user else None),
        "createdAt": v.createdAt,
        "updatedAt": v.updatedAt,
    }


async def get_verifications(
    db: Prisma,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    document_type: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    reported_by: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
):
    where: dict = {}
    if document_type:
        where["documentType"] = document_type
    if status:
        where["status"] = status
    if severity:
        where["severity"] = severity
    if reported_by:
        where["reportedBy"] = reported_by
    if search:
        where["OR"] = [
            {"therapist": {"name": {"contains": search, "mode": "insensitive"}}},
            {"documentType": {"contains": search, "mode": "insensitive"}},
        ]

    order: dict = {}
    if sort_by and sort_by in ("therapist", "documentType", "uploaded", "expires", "status", "severity", "createdAt", "updatedAt"):
        if sort_by == "therapist":
            order["therapist"] = {"name": sort_order}
        elif sort_by == "uploaded":
            order["uploaded"] = sort_order
        else:
            order[sort_by] = sort_order
    else:
        order["createdAt"] = "desc"

    items = await db.verification.find_many(
        where=where,
        order=order,
        skip=skip,
        take=limit,
        include={"therapist": {"include": {"user": True}}},
    )
    total = await db.verification.count(where=where)
    return [_build_verification_response(v) for v in items], total


async def get_verification(db: Prisma, verification_id: str):
    return await db.verification.find_unique(
        where={"id": verification_id},
        include={"therapist": {"include": {"user": True}}},
    )


async def update_verification(db: Prisma, verification_id: str, data: dict):
    if "expires" in data and data["expires"]:
        try:
            data["expires"] = datetime.fromisoformat(data["expires"])
        except (ValueError, TypeError):
            data.pop("expires", None)
    elif "expires" in data and data["expires"] is None:
        data["expires"] = None

    updated = await db.verification.update(
        where={"id": verification_id},
        data=data,
        include={"therapist": {"include": {"user": True}}},
    )
    return _build_verification_response(updated)


async def create_verification(db: Prisma, data: dict):
    if "expires" in data and data["expires"]:
        try:
            data["expires"] = datetime.fromisoformat(data["expires"])
        except (ValueError, TypeError):
            data.pop("expires", None)
    elif "expires" in data and data["expires"] is None:
        data.pop("expires", None)

    created = await db.verification.create(
        data=data,
        include={"therapist": {"include": {"user": True}}},
    )
    return _build_verification_response(created)


async def delete_verification(db: Prisma, verification_id: str):
    await db.verification.delete(where={"id": verification_id})
