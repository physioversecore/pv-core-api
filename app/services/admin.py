from datetime import datetime, timedelta, timezone

from prisma import Prisma


STATUS_MAP = {
    "APPROVED": "Verified",
    "PENDING": "Under review",
    "REJECTED": "Suspended",
}

STATUS_REVERSE_MAP = {v: k for k, v in STATUS_MAP.items()}


async def get_admin_therapists(
    db: Prisma,
    *,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    specialty: str | None = None,
    status: str | None = None,
    city: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
):
    where: dict = {"role": "THERAPIST"}

    if search:
        where["OR"] = [
            {"name": {"contains": search, "mode": "insensitive"}},
            {"email": {"contains": search, "mode": "insensitive"}},
        ]

    if specialty:
        where["therapist"] = {"specialty": {"contains": specialty, "mode": "insensitive"}}

    if city:
        where["city"] = {"contains": city, "mode": "insensitive"}

    if status:
        db_status = STATUS_REVERSE_MAP.get(status)
        if db_status:
            where["status"] = db_status

    needs_post_sort = sort_by in ("sessions", "status")

    order: dict = {"createdAt": "desc"}
    if not needs_post_sort:
        if sort_by == "name":
            order = {"name": sort_order}
        elif sort_by == "city":
            order = {"city": sort_order}
        elif sort_by == "specialty":
            order = {"therapist": {"specialty": sort_order}}
        elif sort_by == "rating":
            order = {"therapist": {"rating": sort_order}}
        elif sort_by == "joined":
            order = {"createdAt": sort_order}

    total = await db.user.count(where=where)

    users = await db.user.find_many(
        where=where,
        include={"therapist": True},
        skip=None if needs_post_sort else skip,
        take=None if needs_post_sort else limit,
        order=order,
    )

    items = []
    for u in users:
        t = u.therapist
        sessions = 0
        if t:
            sessions = await db.session.count(where={"therapistId": t.id})

        items.append({
            "id": t.id if t else u.id,
            "name": u.name,
            "city": t.city if t else (u.city or ""),
            "specialty": t.specialty if t else (u.specialty or ""),
            "rating": t.rating if t else 0.0,
            "sessions": sessions,
            "status": STATUS_MAP.get(u.status, u.status),
            "joined": u.createdAt.strftime("%Y-%m-%d") if u.createdAt else "",
            "isActive": u.status == "APPROVED",
            "phone": u.phone,
            "email": u.email,
            "gender": t.gender if t else None,
            "price": t.price if t else None,
            "experience": t.experience if t else None,
            "bio": t.bio if t else None,
            "mediaUrls": t.mediaUrls if t else None,
        })

    if needs_post_sort:
        reverse = sort_order == "desc"
        items.sort(key=lambda x: x[sort_by] if sort_by else "", reverse=reverse)
        items = items[skip:skip + limit]

    return items, total


async def get_admin_therapist(db: Prisma, therapist_id: str):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return None
    u = await db.user.find_unique(where={"id": t.userId})
    if not u:
        return None
    sessions = await db.session.count(where={"therapistId": t.id})
    return {
        "id": t.id,
        "name": u.name,
        "city": t.city,
        "specialty": t.specialty,
        "rating": t.rating,
        "sessions": sessions,
        "status": STATUS_MAP.get(u.status, u.status),
        "joined": u.createdAt.strftime("%Y-%m-%d") if u.createdAt else "",
        "isActive": u.status == "APPROVED",
        "phone": u.phone,
        "email": u.email,
        "gender": t.gender,
        "price": t.price,
        "experience": t.experience,
        "bio": t.bio,
        "mediaUrls": t.mediaUrls,
    }


async def update_admin_therapist(db: Prisma, therapist_id: str, data: dict):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return None

    therapist_fields = {}
    user_fields = {}

    for field in ("name", "city", "specialty"):
        if field in data and data[field] is not None:
            therapist_fields[field] = data[field]

    if "phone" in data:
        user_fields["phone"] = data["phone"]
    if "email" in data:
        user_fields["email"] = data["email"]
    if "status" in data:
        db_status = STATUS_REVERSE_MAP.get(data["status"])
        if db_status:
            user_fields["status"] = db_status
    if "isActive" in data:
        user_fields["status"] = "APPROVED" if data["isActive"] else "REJECTED"

    if therapist_fields:
        await db.therapist.update(where={"id": therapist_id}, data=therapist_fields)
    if user_fields:
        await db.user.update(where={"id": t.userId}, data=user_fields)

    return await get_admin_therapist(db, therapist_id)


async def delete_admin_therapist(db: Prisma, therapist_id: str):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return False
    await db.therapist.delete(where={"id": therapist_id})
    await db.user.delete(where={"id": t.userId})
    return True


async def get_admin_patients(
    db: Prisma,
    *,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    city: str | None = None,
    therapist_id: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
):
    where: dict = {"role": "PATIENT"}

    if search:
        where["OR"] = [
            {"name": {"contains": search, "mode": "insensitive"}},
            {"email": {"contains": search, "mode": "insensitive"}},
        ]

    if city:
        where["city"] = {"contains": city, "mode": "insensitive"}

    if status == "Active":
        where["status"] = "APPROVED"
    elif status == "Inactive":
        where["status"] = "REJECTED"

    if date_from:
        from datetime import datetime as dt
        try:
            parsed = dt.strptime(date_from, "%Y-%m-%d")
            where.setdefault("createdAt", {})["gte"] = parsed
        except ValueError:
            pass

    if date_to:
        from datetime import datetime as dt
        try:
            parsed = dt.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            where.setdefault("createdAt", {})["lte"] = parsed
        except ValueError:
            pass

    needs_post_sort = sort_by in ("city", "sessions", "therapist", "isActive")

    order: dict = {"createdAt": "desc"}
    if not needs_post_sort:
        if sort_by == "name":
            order = {"name": sort_order}
        elif sort_by == "joined":
            order = {"createdAt": sort_order}

    total = await db.user.count(where=where)

    users = await db.user.find_many(
        where=where,
        skip=None if needs_post_sort else skip,
        take=None if needs_post_sort else limit,
        order=order,
    )

    items = []
    for u in users:
        sessions_raw = await db.session.find_many(
            where={"patientId": u.id},
            include={"therapist": True},
        )
        session_count = len(sessions_raw)

        therapist_name = ""
        therapist_id_val = ""
        if sessions_raw:
            last_session = max(sessions_raw, key=lambda s: s.date if s.date else s.createdAt)
            if last_session.therapist:
                therapist_name = last_session.therapist.name
                therapist_id_val = last_session.therapist.id

        if therapist_id and therapist_id_val != therapist_id:
            continue

        items.append({
            "id": u.id,
            "name": u.name,
            "city": u.city or "",
            "sessions": session_count,
            "therapist": therapist_name,
            "therapistId": therapist_id_val,
            "joined": u.createdAt.strftime("%Y-%m-%d") if u.createdAt else "",
            "isActive": u.status == "APPROVED",
            "phone": u.phone,
            "email": u.email,
        })

    if therapist_id:
        total = len(items)

    if needs_post_sort:
        reverse = sort_order == "desc"
        items.sort(key=lambda x: x[sort_by] if sort_by else "", reverse=reverse)
        items = items[skip:skip + limit]

    return items, total


async def get_admin_patient(db: Prisma, patient_id: str):
    u = await db.user.find_unique(where={"id": patient_id})
    if not u or u.role != "PATIENT":
        return None

    sessions_raw = await db.session.find_many(
        where={"patientId": u.id},
        include={"therapist": True},
    )
    session_count = len(sessions_raw)

    therapist_name = ""
    therapist_id_val = ""
    if sessions_raw:
        last_session = max(sessions_raw, key=lambda s: s.date if s.date else s.createdAt)
        if last_session.therapist:
            therapist_name = last_session.therapist.name
            therapist_id_val = last_session.therapist.id

    return {
        "id": u.id,
        "name": u.name,
        "city": u.city or "",
        "sessions": session_count,
        "therapist": therapist_name,
        "therapistId": therapist_id_val,
        "joined": u.createdAt.strftime("%Y-%m-%d") if u.createdAt else "",
        "isActive": u.status == "APPROVED",
        "phone": u.phone,
        "email": u.email,
    }


async def update_admin_patient(db: Prisma, patient_id: str, data: dict):
    u = await db.user.find_unique(where={"id": patient_id})
    if not u or u.role != "PATIENT":
        return None

    user_fields = {}
    if "name" in data and data["name"] is not None:
        user_fields["name"] = data["name"]
    if "city" in data and data["city"] is not None:
        user_fields["city"] = data["city"]
    if "phone" in data:
        user_fields["phone"] = data["phone"]
    if "email" in data:
        user_fields["email"] = data["email"]
    if "isActive" in data:
        user_fields["status"] = "APPROVED" if data["isActive"] else "REJECTED"

    if user_fields:
        await db.user.update(where={"id": patient_id}, data=user_fields)

    return await get_admin_patient(db, patient_id)


async def delete_admin_patient(db: Prisma, patient_id: str):
    u = await db.user.find_unique(where={"id": patient_id})
    if not u or u.role != "PATIENT":
        return False
    await db.user.delete(where={"id": patient_id})
    return True


async def get_admin_dashboard_stats(db: Prisma) -> dict:
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())

    total_therapists = await db.user.count(where={"role": "THERAPIST"})
    total_patients = await db.user.count(where={"role": "PATIENT"})
    sessions_this_week = await db.session.count(
        where={"date": {"gte": week_start.replace(tzinfo=None)}}
    )
    pending_verifications = await db.user.count(
        where={"role": "THERAPIST", "status": "PENDING"}
    )

    return {
        "total_therapists": total_therapists,
        "total_patients": total_patients,
        "sessions_this_week": sessions_this_week,
        "pending_verifications": pending_verifications,
    }


async def get_admin_earnings(db: Prisma) -> dict:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    payments = await db.payment.find_many(
        where={
            "status": "PENDING",
            "createdAt": {"gte": month_start.replace(tzinfo=None)},
        }
    )
    total = sum(p.amount for p in payments)

    return {
        "platform_earnings": total,
        "description": "Platform fees collected this month",
    }


async def get_admin_recent_activity(db: Prisma, limit: int = 10) -> list[dict]:
    sessions = await db.session.find_many(
        order={"createdAt": "desc"},
        take=limit,
        include={"therapist": True, "patient": True},
    )

    activities = []
    for s in sessions:
        status_map = {
            "SCHEDULED": "booked",
            "COMPLETED": "completed",
            "CANCELLED": "cancelled",
            "RESCHEDULE_REQUESTED": "rescheduled",
        }
        activities.append({
            "id": s.id,
            "patient_name": s.patient.name if s.patient else "Unknown",
            "therapist_name": s.therapist.name if s.therapist else "Unknown",
            "type": status_map.get(s.status, s.status.lower()),
            "timestamp": s.createdAt.isoformat(),
        })

    return activities


SESSION_STATUS_MAP = {
    "SCHEDULED": "Confirmed",
    "IN_PROGRESS": "Confirmed",
    "COMPLETED": "Confirmed",
    "CANCELLED": "Cancelled",
    "RESCHEDULE_REQUESTED": "Rescheduled",
    "DECLINE_REQUESTED": "Cancelled",
}

SESSION_TYPE_MAP = {
    "HOME_VISIT": "Home Visit",
    "CLINIC": "Clinic Visit",
}


async def get_admin_bookings(
    db: Prisma,
    *,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
):
    where: dict = {}

    if search:
        where["OR"] = [
            {"patient": {"name": {"contains": search, "mode": "insensitive"}}},
            {"therapist": {"name": {"contains": search, "mode": "insensitive"}}},
        ]

    if status:
        db_statuses = []
        for db_status, display in SESSION_STATUS_MAP.items():
            if display == status:
                db_statuses.append(db_status)
        if db_statuses:
            where["status"] = {"in": db_statuses}

    if date_from:
        from datetime import datetime as dt
        try:
            parsed = dt.strptime(date_from, "%Y-%m-%d")
            where.setdefault("date", {})["gte"] = parsed
        except ValueError:
            pass

    if date_to:
        from datetime import datetime as dt
        try:
            parsed = dt.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            where.setdefault("date", {})["lte"] = parsed
        except ValueError:
            pass

    needs_post_sort = sort_by in ("patient", "therapist", "sessionType", "paymentStatus")

    order: dict = {"date": sort_order}
    if not needs_post_sort:
        if sort_by == "date":
            order = {"date": sort_order}
        elif sort_by == "originalTime":
            order = {"time": sort_order}
        elif sort_by == "status":
            order = {"status": sort_order}

    total = await db.session.count(where=where)

    sessions = await db.session.find_many(
        where=where,
        skip=None if needs_post_sort else skip,
        take=None if needs_post_sort else limit,
        order=order,
        include={"therapist": True, "patient": True},
    )

    payment_map: dict[str, dict] = {}
    session_ids = [s.id for s in sessions]
    if session_ids:
        payments = await db.payment.find_many(
            where={"sessionId": {"in": session_ids}},
        )
        for p in payments:
            payment_map[p.sessionId] = {
                "status": p.status,
                "method": p.method or "",
            }

    items = []
    for s in sessions:
        therapist = s.therapist
        patient = s.patient
        therapy_user = None
        if therapist:
            therapy_user = await db.user.find_unique(where={"id": therapist.userId})

        payment = payment_map.get(s.id, {})

        items.append({
            "id": s.id,
            "patient": patient.name if patient else "",
            "patientId": s.patientId,
            "patientPhone": patient.phone if patient else "",
            "therapist": therapy_user.name if therapy_user else "",
            "therapistId": s.therapistId,
            "therapistPhone": therapy_user.phone if therapy_user else "",
            "date": s.date.strftime("%Y-%m-%d") if s.date else "",
            "originalTime": s.time or "",
            "sessionType": SESSION_TYPE_MAP.get(s.type, s.type),
            "status": SESSION_STATUS_MAP.get(s.status, s.status),
            "paymentStatus": payment.get("status", ""),
            "paymentMethod": payment.get("method", ""),
        })

    if needs_post_sort:
        reverse = sort_order == "desc"
        items.sort(key=lambda x: x.get(sort_by, "") or "", reverse=reverse)
        items = items[skip:skip + limit]

    return items, total


# ── Performance ──

PERFORMANCE_STATUS_MAP = {
    "Good standing": "APPROVED",
    "Needs review": "PENDING",
    "Under probation": "REJECTED",
    "Escalated": "REJECTED",
    "Resolved": "APPROVED",
    "Removed": "REJECTED",
}


async def get_admin_performance(
    db: Prisma,
    *,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    min_rating: float | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
):
    where: dict = {"role": "THERAPIST"}

    if search:
        where["OR"] = [
            {"name": {"contains": search, "mode": "insensitive"}},
            {"email": {"contains": search, "mode": "insensitive"}},
        ]

    needs_post_sort = sort_by in ("sessions", "reviews", "trend", "linkedComplaints", "status", "avgRating")

    order: dict = {"name": sort_order}
    if not needs_post_sort:
        if sort_by == "name":
            order = {"name": sort_order}

    total = await db.user.count(where=where)

    users = await db.user.find_many(
        where=where,
        include={"therapist": True},
        skip=None if needs_post_sort else skip,
        take=None if needs_post_sort else limit,
        order=order,
    )

    items = []
    for u in users:
        t = u.therapist
        sessions = 0
        reviews_count = 0
        avg_rating = 0.0
        trend = 0.0
        linked_complaints = 0

        if t:
            db_sessions = await db.session.count(where={"therapistId": t.id})
            db_reviews_count = await db.review.count(where={"therapistId": t.id})
            avg_rating = t.rating

            completed_sessions = await db.session.count(
                where={"therapistId": t.id, "status": "COMPLETED"}
            )
            if completed_sessions > 0:
                trend = round((db_sessions - completed_sessions) / max(completed_sessions, 1), 1)

            db_linked_complaints = await db.complaint.count(
                where={"againstId": t.id}
            )

            sessions = t.sessionsOverride if t.sessionsOverride is not None else db_sessions
            reviews_count = t.reviewsOverride if t.reviewsOverride is not None else db_reviews_count
            trend = t.trendOverride if t.trendOverride is not None else trend
            linked_complaints = t.linkedComplaintsOverride if t.linkedComplaintsOverride is not None else db_linked_complaints

        perf_status = _derive_performance_status(avg_rating, linked_complaints, u.status)

        if t and t.statusOverride is not None:
            perf_status = t.statusOverride

        if status and perf_status != status:
            continue
        if min_rating is not None and avg_rating < min_rating:
            continue

        items.append({
            "id": t.id if t else u.id,
            "name": u.name,
            "avgRating": avg_rating,
            "sessions": sessions,
            "reviews": reviews_count,
            "trend": trend,
            "linkedComplaints": linked_complaints,
            "status": perf_status,
        })

    if needs_post_sort:
        reverse = sort_order == "desc"
        items.sort(key=lambda x: x.get(sort_by, "") or "", reverse=reverse)
        total = len(items)
        items = items[skip:skip + limit]

    return items, total


def _derive_performance_status(avg_rating: float, linked_complaints: int, user_status: str) -> str:
    if linked_complaints >= 3:
        return "Under probation"
    if avg_rating < 4.0:
        return "Under probation"
    if avg_rating < 4.5 or linked_complaints > 0:
        return "Needs review"
    return "Good standing"


async def get_admin_performance_detail(db: Prisma, therapist_id: str):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return None
    u = await db.user.find_unique(where={"id": t.userId})
    if not u:
        return None

    db_sessions = await db.session.count(where={"therapistId": t.id})
    db_reviews_count = await db.review.count(where={"therapistId": t.id})
    db_linked_complaints = await db.complaint.count(where={"againstId": t.id})

    completed_sessions = await db.session.count(
        where={"therapistId": t.id, "status": "COMPLETED"}
    )
    trend = 0.0
    if completed_sessions > 0:
        trend = round((db_sessions - completed_sessions) / max(completed_sessions, 1), 1)

    sessions = t.sessionsOverride if t.sessionsOverride is not None else db_sessions
    reviews_count = t.reviewsOverride if t.reviewsOverride is not None else db_reviews_count
    trend = t.trendOverride if t.trendOverride is not None else trend
    linked_complaints = t.linkedComplaintsOverride if t.linkedComplaintsOverride is not None else db_linked_complaints

    perf_status = _derive_performance_status(t.rating, linked_complaints, u.status)
    if t.statusOverride is not None:
        perf_status = t.statusOverride

    return {
        "id": t.id,
        "name": u.name,
        "avgRating": t.rating,
        "sessions": sessions,
        "reviews": reviews_count,
        "trend": trend,
        "linkedComplaints": linked_complaints,
        "status": perf_status,
    }


async def update_admin_performance(db: Prisma, therapist_id: str, data: dict):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return None

    therapist_fields = {}
    user_fields = {}

    if "name" in data and data["name"] is not None:
        user_fields["name"] = data["name"]
        therapist_fields["name"] = data["name"]
    if "avgRating" in data and data["avgRating"] is not None:
        therapist_fields["rating"] = data["avgRating"]
    if "sessions" in data and data["sessions"] is not None:
        therapist_fields["sessionsOverride"] = data["sessions"]
    if "reviews" in data and data["reviews"] is not None:
        therapist_fields["reviewsOverride"] = data["reviews"]
    if "trend" in data and data["trend"] is not None:
        therapist_fields["trendOverride"] = data["trend"]
    if "linkedComplaints" in data and data["linkedComplaints"] is not None:
        therapist_fields["linkedComplaintsOverride"] = data["linkedComplaints"]
    if "status" in data and data["status"] is not None:
        therapist_fields["statusOverride"] = data["status"]
        db_status = PERFORMANCE_STATUS_MAP.get(data["status"])
        if db_status:
            user_fields["status"] = db_status

    if therapist_fields:
        await db.therapist.update(where={"id": therapist_id}, data=therapist_fields)
    if user_fields:
        await db.user.update(where={"id": t.userId}, data=user_fields)

    return await get_admin_performance_detail(db, therapist_id)


async def resolve_therapist(db: Prisma, therapist_id: str):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return None

    await db.user.update(
        where={"id": t.userId},
        data={"status": "APPROVED"},
    )
    await db.therapist.update(
        where={"id": therapist_id},
        data={"statusOverride": None},
    )

    return await get_admin_performance_detail(db, therapist_id)


async def schedule_review(db: Prisma, therapist_id: str, data: dict):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return None

    return {
        "success": True,
        "message": f"Review scheduled for {data.get('date', 'TBD')}",
        "therapistId": therapist_id,
        "date": data.get("date"),
        "adminId": data.get("adminId"),
        "notes": data.get("notes", ""),
    }


async def remove_from_team(db: Prisma, therapist_id: str, reason: str = ""):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return None

    await db.user.update(
        where={"id": t.userId},
        data={"status": "REJECTED"},
    )
    await db.therapist.update(
        where={"id": therapist_id},
        data={"statusOverride": "Removed"},
    )

    return {
        "success": True,
        "message": f"Therapist removed from team. Reason: {reason}" if reason else "Therapist removed from team",
        "therapistId": therapist_id,
    }


async def delete_admin_performance(db: Prisma, therapist_id: str):
    t = await db.therapist.find_unique(where={"id": therapist_id})
    if not t:
        return False

    await db.therapist.delete(where={"id": therapist_id})
    await db.user.delete(where={"id": t.userId})
    return True


async def create_therapist_by_admin(db: Prisma, data: dict):
    from app.services.auth import hash_password

    password = hash_password(data["password"])

    user = await db.user.create(
        data={
            "name": data["name"],
            "email": data["email"],
            "password": password,
            "role": "THERAPIST",
            "city": data["city"],
            "phone": data.get("phone"),
            "specialty": data["specialty"],
            "status": "APPROVED",
        }
    )

    therapist = await db.therapist.create(
        data={
            "userId": user.id,
            "name": data["name"],
            "specialty": data["specialty"],
            "city": data["city"],
            "gender": data["gender"],
            "price": data["price"],
            "experience": data["experience"],
            "bio": data.get("bio", ""),
        }
    )

    doc_types = []
    if data.get("citizenshipNumber"):
        doc_types.append(("Government ID", data["citizenshipNumber"]))
    if data.get("panNumber"):
        doc_types.append(("PAN Card", data["panNumber"]))
    if data.get("medicalLicenseUrl"):
        doc_types.append(("Practice license", data["medicalLicenseUrl"]))
    if data.get("certificateUrl"):
        doc_types.append(("Certification", data["certificateUrl"]))

    for doc_type, doc_value in doc_types:
        await db.verification.create(
            data={
                "therapistId": therapist.id,
                "documentType": doc_type,
                "status": "Pending review",
                "reportedBy": "Admin",
                "phone": data.get("phone"),
            }
        )

    return {
        "id": therapist.id,
        "userId": user.id,
        "name": therapist.name,
        "email": user.email,
        "phone": user.phone,
        "city": therapist.city,
        "specialty": therapist.specialty,
        "gender": therapist.gender,
        "price": therapist.price,
        "experience": therapist.experience,
        "bio": therapist.bio,
        "createdAt": therapist.createdAt.isoformat() if therapist.createdAt else "",
        "updatedAt": therapist.updatedAt.isoformat() if therapist.updatedAt else "",
    }
