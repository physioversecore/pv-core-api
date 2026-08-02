from datetime import datetime, timedelta

from prisma import Prisma

from app.services.patient import generate_referral_code


async def get_therapists(
    db: Prisma,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    city: str | None = None,
    specialty: str | None = None,
    gender: str | None = None,
):
    where = {}
    if search:
        where["name"] = {"contains": search, "mode": "insensitive"}
    if city:
        where["city"] = city
    if specialty:
        where["specialty"] = specialty
    if gender:
        where["gender"] = gender

    therapists = await db.therapist.find_many(
        where=where,
        skip=skip,
        take=limit,
        order={"createdAt": "desc"},
    )
    total = await db.therapist.count(where=where)
    return therapists, total


async def get_therapist(db: Prisma, therapist_id: str):
    return await db.therapist.find_unique(where={"id": therapist_id})


async def get_therapist_by_user(db: Prisma, user_id: str):
    return await db.therapist.find_unique(where={"userId": user_id})


async def create_therapist(db: Prisma, user_id: str, data: dict):
    return await db.therapist.create(data={"userId": user_id, **data})


async def update_therapist(db: Prisma, therapist_id: str, data: dict):
    return await db.therapist.update(where={"id": therapist_id}, data=data)


async def get_therapist_profile(db: Prisma, user_id: str):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        return None
    therapist = await db.therapist.find_unique(where={"userId": user_id})
    if not therapist:
        return None

    verifications = await db.verification.find_many(
        where={"therapistId": therapist.id},
        order={"createdAt": "desc"},
    )
    documents = [
        {
            "id": v.id,
            "documentType": v.documentType,
            "documentUrl": v.documentUrl,
            "fileName": v.fileName,
            "fileSize": v.fileSize,
            "status": v.status,
            "note": v.note,
        }
        for v in verifications
    ]

    return {
        "id": therapist.id,
        "userId": user.id,
        "name": therapist.name or user.name,
        "email": user.email,
        "phone": user.phone or "",
        "city": therapist.city or "",
        "specialty": therapist.specialty or "General",
        "gender": therapist.gender or "Male",
        "price": therapist.price or 0.0,
        "experience": therapist.experience or 0,
        "bio": therapist.bio or "",
        "mediaUrls": therapist.mediaUrls,
        "photo": (therapist.mediaUrls or "").split(",")[0].strip() or None,
        "documents": documents,
    }


async def update_therapist_profile(db: Prisma, user_id: str, data: dict):
    user_fields = {}
    therapist_fields = {}

    user_field_keys = {"name", "phone", "city", "specialty"}
    therapist_field_keys = {"name", "city", "specialty", "gender", "price", "experience", "bio", "mediaUrls"}

    for key, value in data.items():
        if key in user_field_keys and value is not None:
            user_fields[key] = value
        if key in therapist_field_keys and value is not None:
            therapist_fields[key] = value

    if user_fields:
        await db.user.update(where={"id": user_id}, data=user_fields)

    existing = await db.therapist.find_unique(where={"userId": user_id})
    if existing:
        if therapist_fields:
            await db.therapist.update(where={"userId": user_id}, data=therapist_fields)
    else:
        user = await db.user.find_unique(where={"id": user_id})
        create_data = {
            "userId": user_id,
            "name": therapist_fields.get("name") or (user.name if user else "Therapist"),
            "specialty": therapist_fields.get("specialty") or (user.specialty if user and user.specialty else "General"),
            "city": therapist_fields.get("city") or (user.city if user and user.city else "Kathmandu"),
            "gender": therapist_fields.get("gender") or "Male",
            "price": therapist_fields.get("price") or 1000.0,
            "experience": therapist_fields.get("experience") or 1,
            "bio": therapist_fields.get("bio") or "",
        }
        await db.therapist.create(data=create_data)

    return await get_therapist_profile(db, user_id)


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
            "address": s.address or "",
            "type": s.type,
            "status": "Confirmed" if s.status == "SCHEDULED" else "Pending",
        }
        for s in today_sessions_raw
    ]

    recent_reports_raw = await db.report.find_many(
        where={"therapistId": therapist.id},
        include={"patient": True},
        order={"createdAt": "desc"},
        take=5,
    )
    recent_reports = [
        {
            "id": r.id,
            "patient": r.patient.name if r.patient else "Unknown",
            "kind": _detect_report_kind(r),
            "title": r.title or "",
            "content": r.content or "",
            "files": [u.strip() for u in r.fileUrl.split(",") if u.strip()] if r.fileUrl else [],
            "date": r.createdAt.strftime("%-d %b") if r.createdAt else "",
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
        "name": user.name or "Therapist",
        "sessionsThisWeek": sessions_this_week,
        "totalPatients": total_patients,
        "earningsThisMonth": earnings,
        "averageRating": therapist.rating or 0.0,
        "todaySessions": today_sessions,
        "recentUploads": recent_reports,
        "publicProfile": {
            "name": therapist.name or user.name or "Therapist",
            "specialty": therapist.specialty or "General",
            "experience": therapist.experience or 0,
            "rating": therapist.rating or 0.0,
            "totalReviews": therapist.reviews or 0,
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
