from prisma import Prisma


def _enrich_session(s):
    d = s.model_dump() if hasattr(s, "model_dump") else vars(s)
    d["therapistName"] = s.therapist.name if hasattr(s, "therapist") and s.therapist else ""
    patient = getattr(s, "patient", None)
    d["patientName"] = patient.name if patient else ""
    d["patientPhone"] = patient.phone if patient else ""
    return d


def _enrich_sessions(sessions: list):
    return [_enrich_session(s) for s in sessions]


async def create_session(db: Prisma, data: dict):
    session = await db.session.create(data=data, include={"therapist": True})
    return _enrich_session(session)


async def get_sessions_for_patient(db: Prisma, patient_id: str, skip=0, limit=100):
    sessions = await db.session.find_many(
        where={"patientId": patient_id},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
        include={"therapist": True},
    )
    total = await db.session.count(where={"patientId": patient_id})
    return _enrich_sessions(sessions), total


async def get_sessions_for_therapist(db: Prisma, therapist_id: str, skip=0, limit=100):
    sessions = await db.session.find_many(
        where={"therapistId": therapist_id},
        skip=skip,
        take=limit,
        order={"date": "asc"},
        include={"therapist": True, "patient": True},
    )
    total = await db.session.count(where={"therapistId": therapist_id})
    return _enrich_sessions(sessions), total


async def get_all_sessions(db: Prisma, skip=0, limit=100):
    sessions = await db.session.find_many(
        skip=skip, take=limit, order={"createdAt": "desc"},
        include={"therapist": True},
    )
    total = await db.session.count()
    return _enrich_sessions(sessions), total


async def get_session(db: Prisma, session_id: str):
    session = await db.session.find_unique(where={"id": session_id}, include={"therapist": True})
    return _enrich_session(session) if session else None


async def update_session(db: Prisma, session_id: str, data: dict):
    session = await db.session.update(where={"id": session_id}, data=data, include={"therapist": True, "patient": True})
    return _enrich_session(session)


async def delete_session(db: Prisma, session_id: str):
    await db.session.delete(where={"id": session_id})


async def reschedule_session(
    db: Prisma, session_id: str, patient_id: str, new_date: str, new_time: str
):
    from datetime import datetime as dt

    session = await db.session.find_unique(
        where={"id": session_id}, include={"therapist": True}
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

    therapist_user_id = session.therapist.userId if hasattr(session.therapist, "userId") else session.therapistId
    from app.services.availability import _get_wh, _generate_slots

    wh = await _get_wh(db, therapist_user_id)
    step = wh.get("sessionDuration", 60) + wh.get("breakDuration", 0)
    valid_times = set(_generate_slots(wh["start"], wh["end"], step))
    if new_time not in valid_times:
        return None, "Invalid time slot for this therapist"

    updated = await db.session.update(
        where={"id": session_id},
        data={"date": dt.strptime(new_date, "%Y-%m-%d"), "time": new_time},
        include={"therapist": True, "patient": True},
    )
    return _enrich_session(updated), None
