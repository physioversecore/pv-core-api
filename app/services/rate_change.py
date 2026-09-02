from prisma import Prisma
from fastapi import HTTPException


_STATUS_VALUES = {"PENDING", "APPROVED", "REJECTED"}


async def create_rate_change(db: Prisma, therapist_id: str, data: dict) -> dict:
    """Create a pending session-rate change request for admin verification."""
    therapist = await db.therapist.find_unique(where={"id": therapist_id})
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")

    rate_to = float(data["rate_to"])
    if rate_to <= (therapist.price or 0):
        raise HTTPException(
            status_code=400,
            detail="Requested rate must be higher than the current rate",
        )

    request = await db.ratechangerequest.create(
        data={
            "therapistId": therapist_id,
            "rateFrom": therapist.price or 0,
            "rateTo": rate_to,
            "reason": data.get("reason", ""),
            "status": "PENDING",
        }
    )
    return {
        "id": request.id,
        "status": request.status,
        "rateFrom": request.rateFrom,
        "rateTo": request.rateTo,
        "createdAt": request.createdAt.isoformat(),
    }


async def _serialize(db: Prisma, requests) -> list[dict]:
    result = []
    for r in requests:
        therapist = await db.therapist.find_unique(where={"id": r.therapistId})
        user = (
            await db.user.find_unique(where={"id": therapist.userId})
            if therapist
            else None
        )
        result.append(
            {
                "id": r.id,
                "therapistId": r.therapistId,
                "therapistName": therapist.name if therapist else "",
                "therapistEmail": user.email if user else "",
                "rateFrom": r.rateFrom,
                "rateTo": r.rateTo,
                "reason": r.reason,
                "status": r.status,
                "adminNotes": r.adminNotes,
                "createdAt": r.createdAt.isoformat(),
            }
        )
    return result


async def get_therapist_rate_changes(db: Prisma, therapist_id: str) -> list[dict]:
    rows = await db.ratechangerequest.find_many(
        where={"therapistId": therapist_id},
        order={"createdAt": "desc"},
        take=20,
    )
    return await _serialize(db, rows)


async def get_rate_changes_for_admin(
    db: Prisma,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> tuple[list[dict], int]:
    where: dict = {}
    if status and status.upper() in _STATUS_VALUES:
        where["status"] = status.upper()
    total = await db.ratechangerequest.count(where=where)
    rows = await db.ratechangerequest.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )
    return await _serialize(db, rows), total


async def approve_rate_change(db: Prisma, request_id: str, admin_notes: str = "") -> dict:
    request = await db.ratechangerequest.find_unique(where={"id": request_id})
    if not request:
        return {"success": False, "error": "Request not found"}
    if request.status != "PENDING":
        return {"success": False, "error": "Request already decided"}

    therapist = await db.therapist.find_unique(where={"id": request.therapistId})
    if not therapist:
        return {"success": False, "error": "Therapist not found"}

    await db.therapist.update(
        where={"id": therapist.id}, data={"price": request.rateTo}
    )
    await db.ratechangerequest.update(
        where={"id": request_id},
        data={"status": "APPROVED", "adminNotes": admin_notes},
    )
    return {"success": True, "therapistId": therapist.id, "newRate": request.rateTo}


async def reject_rate_change(db: Prisma, request_id: str, admin_notes: str = "") -> dict:
    request = await db.ratechangerequest.find_unique(where={"id": request_id})
    if not request:
        return {"success": False, "error": "Request not found"}
    if request.status != "PENDING":
        return {"success": False, "error": "Request already decided"}

    await db.ratechangerequest.update(
        where={"id": request_id},
        data={"status": "REJECTED", "adminNotes": admin_notes},
    )
    return {"success": True}