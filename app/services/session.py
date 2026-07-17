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
