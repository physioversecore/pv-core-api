import secrets
import string

from prisma import Prisma


def generate_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(8))
    return f"SAHA-{suffix}"


async def get_patient_dashboard(db: Prisma, user_id: str):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return None

    total_sessions = await db.session.count(where={"patientId": user_id})
    completed_sessions = await db.session.count(
        where={"patientId": user_id, "status": "COMPLETED"}
    )
    upcoming_sessions = await db.session.count(
        where={"patientId": user_id, "status": "SCHEDULED"}
    )

    session = await db.session.find_first(
        where={"patientId": user_id, "status": "SCHEDULED"},
        order={"date": "asc"},
    )

    next_session = None
    if session:
        therapist = await db.therapist.find_unique(
            where={"id": session.therapistId}
        )
        next_session = {
            "id": session.id,
            "therapistName": therapist.name if therapist else "Unknown",
            "therapistId": session.therapistId,
            "date": session.date.isoformat(),
            "time": session.time,
            "type": session.type,
            "status": session.status,
        }

    code = user.referralCode
    if not code:
        code = generate_referral_code()
        await db.user.update(
            where={"id": user_id}, data={"referralCode": code}
        )

    link = f"https://sahayatri.np/r/{code}"

    return {
        "name": user.name,
        "totalSessions": total_sessions,
        "completedSessions": completed_sessions,
        "upcomingSessions": upcoming_sessions,
        "nextSession": next_session,
        "referralCode": code,
        "referralLink": link,
    }


async def get_patient_referral(db: Prisma, user_id: str):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return None

    code = user.referralCode
    if not code:
        code = generate_referral_code()
        await db.user.update(
            where={"id": user_id}, data={"referralCode": code}
        )

    link = f"https://sahayatri.np/r/{code}"
    return {"code": code, "link": link}
