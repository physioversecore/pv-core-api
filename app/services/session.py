from prisma import Prisma


def _enrich_session(s):
    if s is None:
        return {"id": "", "therapistName": "", "patientName": "", "patientPhone": ""}
    try:
        d = s.model_dump() if hasattr(s, "model_dump") else vars(s)
        d["therapistName"] = ""
        if hasattr(s, "therapist") and s.therapist:
            d["therapistName"] = s.therapist.name if s.therapist.name else ""
        patient = getattr(s, "patient", None)
        d["patientName"] = patient.name if patient and patient.name else ""
        d["patientPhone"] = patient.phone if patient and patient.phone else ""
        member = getattr(s, "familyMember", None)
        d["familyMemberId"] = getattr(s, "familyMemberId", None)
        d["familyMemberName"] = member.name if member and member.name else None
        purchase = getattr(s, "packagePurchase", None)
        d["bookedViaPackage"] = purchase is not None
        d["packagePurchaseId"] = getattr(s, "packagePurchaseId", None)
        if purchase is not None:
            pkg = getattr(purchase, "package", None)
            d["packageName"] = pkg.name if pkg else None
        else:
            d["packageName"] = None
        return d
    except Exception:
        return {"id": getattr(s, "id", ""), "therapistName": "", "patientName": "", "patientPhone": ""}


def _enrich_sessions(sessions: list):
    return [_enrich_session(s) for s in sessions]


async def validate_family_member(db: Prisma, user_id: str, family_member_id: str | None):
    """Validate that a family member belongs to the given patient. Returns the member or None."""
    if not family_member_id:
        return None
    profile = await db.patientprofile.find_unique(where={"userId": user_id})
    if not profile:
        return None
    member = await db.familymember.find_unique(where={"id": family_member_id})
    if not member or member.patientId != profile.id:
        return None
    return member


async def is_slot_booked(
    db: Prisma,
    therapist_id: str,
    date_obj,
    time_str: str,
    exclude_session_id: str | None = None,
) -> bool:
    """Return True if the therapist/date/time slot is already occupied by an
    active (scheduled or in-progress) session. Used to prevent two patients
    booking the same time slot of the same therapist."""
    from datetime import datetime as dt

    if isinstance(date_obj, str):
        try:
            date_obj = dt.fromisoformat(date_obj)
        except ValueError:
            date_obj = dt.strptime(date_obj, "%Y-%m-%d")
    day_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
    where: dict = {
        "therapistId": therapist_id,
        "date": {"gte": day_start, "lte": day_end},
        "time": time_str,
        "status": {"in": ["SCHEDULED", "IN_PROGRESS"]},
    }
    if exclude_session_id:
        where["id"] = {"not": exclude_session_id}
    existing = await db.session.find_many(where=where, take=1)
    return len(existing) > 0


async def create_session(db: Prisma, data: dict):
    family_member = await validate_family_member(
        db, data.get("patientId"), data.get("familyMemberId")
    )
    if data.get("familyMemberId") and not family_member:
        raise ValueError("Invalid family member")
    if await is_slot_booked(db, data["therapistId"], data["date"], data["time"]):
        raise ValueError("CONFLICT")

    package_purchase_id = data.get("packagePurchaseId")
    if package_purchase_id:
        from app.services.package_purchase import get_active_purchase, deduct_session

        purchase = await db.packagepurchase.find_unique(
            where={"id": package_purchase_id},
            include={"package": True},
        )
        if not purchase or purchase.userId != data["patientId"]:
            raise ValueError("Invalid package purchase")
        if purchase.status != "ACTIVE":
            raise ValueError("PACKAGE_NOT_ACTIVE")
        if purchase.sessionsUsed >= purchase.sessionsTotal:
            raise ValueError("PACKAGE_DEPLETED")
        active = await get_active_purchase(db, data["patientId"])
        if not active or active["id"] != package_purchase_id:
            raise ValueError("PACKAGE_NOT_ACTIVE")

    create_data = {
        "therapistId": data["therapistId"],
        "patientId": data["patientId"],
        "date": data["date"],
        "time": data["time"],
        "type": data.get("type", "HOME_VISIT"),
        "address": data["address"],
        "fee": 0 if package_purchase_id else data["fee"],
        "notes": data.get("notes"),
    }
    if package_purchase_id:
        create_data["packagePurchaseId"] = package_purchase_id
    if family_member:
        create_data["familyMemberId"] = family_member.id
    session = await db.session.create(
        data=create_data,
        include={"therapist": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}},
    )
    if package_purchase_id:
        await deduct_session(db, package_purchase_id)
    return _enrich_session(session)


async def get_sessions_for_patient(db: Prisma, patient_id: str, skip=0, limit=100):
    sessions = await db.session.find_many(
        where={"patientId": patient_id},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={"therapist": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}},
    )
    total = await db.session.count(where={"patientId": patient_id})
    return _enrich_sessions(sessions), total


async def get_sessions_for_therapist(db: Prisma, therapist_id: str, skip=0, limit=100):
    sessions = await db.session.find_many(
        where={"therapistId": therapist_id},
        skip=skip,
        take=limit,
        order={"date": "asc"},
        include={"therapist": True, "patient": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}},
    )
    total = await db.session.count(where={"therapistId": therapist_id})
    return _enrich_sessions(sessions), total


async def get_all_sessions(db: Prisma, skip=0, limit=100):
    sessions = await db.session.find_many(
        skip=skip, take=limit, order={"createdAt": "desc"},
        include={"therapist": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}},
    )
    total = await db.session.count()
    return _enrich_sessions(sessions), total


async def get_session(db: Prisma, session_id: str):
    session = await db.session.find_unique(where={"id": session_id}, include={"therapist": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}})
    return _enrich_session(session) if session else None


async def update_session(db: Prisma, session_id: str, data: dict):
    session = await db.session.update(where={"id": session_id}, data=data, include={"therapist": True, "patient": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}})
    return _enrich_session(session)


async def delete_session(db: Prisma, session_id: str):
    session = await db.session.find_unique(where={"id": session_id})
    if session and session.packagePurchaseId:
        from app.services.package_purchase import restore_session

        await restore_session(db, session.packagePurchaseId)
    await db.session.delete(where={"id": session_id})


async def reschedule_session(
    db: Prisma, session_id: str, patient_id: str, new_date: str, new_time: str
):
    from datetime import datetime as dt

    session = await db.session.find_unique(
        where={"id": session_id},
        include={"therapist": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}},
    )
    if not session:
        return None, "Session not found"
    if session.patientId != patient_id:
        return None, "Not authorized"
    if session.status != "SCHEDULED":
        return None, "Only scheduled sessions can be rescheduled"

    old_date_str = session.date.strftime("%Y-%m-%d")
    if old_date_str == new_date and session.time == new_time:
        return None, "New slot must be different from the current one"

    conflict = await db.session.find_first(
        where={
            "therapistId": session.therapistId,
            "date": dt.strptime(new_date, "%Y-%m-%d"),
            "time": new_time,
            "status": {"in": ["SCHEDULED", "IN_PROGRESS"]},
            "id": {"not": session_id},
        }
    )
    if conflict:
        return None, "CONFLICT"

    therapist_user_id = session.therapist.userId if session.therapist and hasattr(session.therapist, "userId") else session.therapistId
    from app.services.availability import _get_wh, _generate_slots

    wh = await _get_wh(db, therapist_user_id)
    step = wh.get("sessionDuration", 60) + wh.get("breakDuration", 0)
    valid_times = set(_generate_slots(wh["start"], wh["end"], step))
    if new_time not in valid_times:
        return None, "Invalid time slot for this therapist"

    updated = await db.session.update(
        where={"id": session_id},
        data={"date": dt.strptime(new_date, "%Y-%m-%d"), "time": new_time},
        include={"therapist": True, "patient": True, "familyMember": True, "packagePurchase": {"include": {"package": True}}},
    )
    return _enrich_session(updated), None
