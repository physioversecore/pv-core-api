from datetime import datetime, timedelta

from prisma import Prisma

from app.services.patient import generate_referral_code


async def get_therapists(db: Prisma, skip: int = 0, limit: int = 100):
    therapists = await db.therapist.find_many(
        skip=skip, take=limit, order={"createdAt": "desc"}
    )
    total = await db.therapist.count()
    return therapists, total


async def get_therapist(db: Prisma, therapist_id: str):
    return await db.therapist.find_unique(where={"id": therapist_id})


async def get_therapist_by_user(db: Prisma, user_id: str):
    return await db.therapist.find_unique(where={"userId": user_id})


async def create_therapist(db: Prisma, user_id: str, data: dict):
    return await db.therapist.create(data={"userId": user_id, **data})


async def update_therapist(db: Prisma, therapist_id: str, data: dict):
    return await db.therapist.update(where={"id": therapist_id}, data=data)


async def delete_therapist(db: Prisma, therapist_id: str):
    await db.therapist.delete(where={"id": therapist_id})


async def get_therapist_dashboard(db: Prisma, user_id: str):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return None

    therapist = await db.therapist.find_unique(where={"userId": user_id})
    if not therapist:
        return None

    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    sessions_this_week = await db.session.count(
        where={"therapistId": therapist.id, "date": {"gte": week_start}}
    )

    all_sessions = await db.session.find_many(
        where={"therapistId": therapist.id},
    )
    total_patients = len({s.patientId for s in all_sessions})

    completed_this_month = await db.session.find_many(
        where={
            "therapistId": therapist.id,
            "date": {"gte": month_start},
            "status": "COMPLETED",
        },
    )
    earnings = sum(s.fee for s in completed_this_month)

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today + timedelta(days=1)

    today_sessions_raw = await db.session.find_many(
        where={
            "therapistId": therapist.id,
            "date": {"gte": today, "lt": today_end},
            "status": {"in": ["SCHEDULED", "IN_PROGRESS"]},
        },
        include={"patient": True},
        order={"time": "asc"},
    )

    today_sessions = [
        {
            "id": s.id,
            "time": s.time,
            "patient": s.patient.name if s.patient else "Unknown",
            "patientId": s.patientId,
            "address": s.address,
            "type": s.type,
            "status": "Confirmed" if s.status == "SCHEDULED" else "Pending",
        }
        for s in today_sessions_raw
    ]

    patient_ids = list({s.patientId for s in all_sessions})
    recent_reports = []
    if patient_ids:
        recent_reports_raw = await db.report.find_many(
            where={"patientId": {"in": patient_ids[:50]}},
            include={"patient": True},
            order={"createdAt": "desc"},
            take=5,
        )
        recent_reports = [
            {
                "id": r.id,
                "patient": r.patient.name if r.patient else "Unknown",
                "kind": _detect_report_kind(r),
                "title": r.title,
                "file": r.fileUrl or "",
                "date": r.createdAt.strftime("%-d %b"),
            }
            for r in recent_reports_raw
        ]

    recent_reviews_raw = await db.review.find_many(
        where={"therapistId": therapist.id},
        include={"patient": True},
        order={"createdAt": "desc"},
        take=5,
    )
    recent_ratings = [
        {
            "id": rv.id,
            "name": rv.patient.name if rv.patient else "Unknown",
            "stars": rv.rating,
            "text": rv.comment or "",
        }
        for rv in recent_reviews_raw
    ]

    code = user.referralCode
    if not code:
        code = generate_referral_code()
        await db.user.update(where={"id": user_id}, data={"referralCode": code})
    link = f"https://sahayatri.np/join/{code}"

    return {
        "name": user.name,
        "sessionsThisWeek": sessions_this_week,
        "totalPatients": total_patients,
        "earningsThisMonth": earnings,
        "averageRating": therapist.rating,
        "todaySessions": today_sessions,
        "recentUploads": recent_reports,
        "publicProfile": {
            "name": therapist.name,
            "specialty": therapist.specialty,
            "experience": therapist.experience,
            "rating": therapist.rating,
            "totalReviews": therapist.reviews,
        },
        "recentRatings": recent_ratings,
        "referralCode": code,
        "referralLink": link,
    }


def _detect_report_kind(report) -> str:
    if not report.fileUrl:
        return "note"
    ext = report.fileUrl.rsplit(".", 1)[-1].lower() if "." in report.fileUrl else ""
    if ext in ("jpg", "jpeg", "png", "gif", "webp"):
        return "x-ray"
    if ext in ("mp4", "mov", "avi", "webm"):
        return "video"
    return "note"
