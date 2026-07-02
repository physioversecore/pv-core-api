from prisma import Prisma


async def create_session(db: Prisma, data: dict):
    return await db.session.create(data=data)


async def get_sessions_for_patient(db: Prisma, patient_id: str, skip=0, limit=100):
    sessions = await db.session.find_many(
        where={"patientId": patient_id},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )
    total = await db.session.count(where={"patientId": patient_id})
    return sessions, total


async def get_sessions_for_therapist(db: Prisma, therapist_id: str, skip=0, limit=100):
    sessions = await db.session.find_many(
        where={"therapistId": therapist_id},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )
    total = await db.session.count(where={"therapistId": therapist_id})
    return sessions, total


async def get_all_sessions(db: Prisma, skip=0, limit=100):
    sessions = await db.session.find_many(
        skip=skip, take=limit, order={"createdAt": "desc"}
    )
    total = await db.session.count()
    return sessions, total


async def get_session(db: Prisma, session_id: str):
    return await db.session.find_unique(where={"id": session_id})


async def update_session(db: Prisma, session_id: str, data: dict):
    return await db.session.update(where={"id": session_id}, data=data)


async def delete_session(db: Prisma, session_id: str):
    await db.session.delete(where={"id": session_id})
