from prisma import Prisma


async def get_completed_sessions_without_review(db: Prisma, patient_id: str, limit: int = 0):
    reviewed = await db.review.find_many(
        where={"patientId": patient_id},
    )
    reviewed_ids = [r.therapistId for r in reviewed]

    where: dict = {
        "patientId": patient_id,
        "status": "COMPLETED",
        "review": None,
    }
    if reviewed_ids:
        where["therapistId"] = {"notIn": reviewed_ids}

    sessions = await db.session.find_many(
        where=where,
        include={
            "therapist": True,
        },
        order={"date": "desc"},
    )
    seen: set[str] = set()
    unique: list = []
    for s in sessions:
        if s.therapistId not in seen:
            seen.add(s.therapistId)
            unique.append(s)
            if limit and len(unique) >= limit:
                break
    return unique


async def create_review(db: Prisma, data: dict):
    return await db.review.create(data=data)


async def get_review_by_session(db: Prisma, session_id: str):
    return await db.review.find_unique(where={"sessionId": session_id})


async def get_review_by_patient_and_therapist(db: Prisma, patient_id: str, therapist_id: str):
    return await db.review.find_first(
        where={"patientId": patient_id, "therapistId": therapist_id},
    )


async def get_reviews_for_patient(db: Prisma, patient_id: str, skip=0, limit=100):
    reviews = await db.review.find_many(
        where={"patientId": patient_id},
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )
    total = await db.review.count(where={"patientId": patient_id})
    return reviews, total
