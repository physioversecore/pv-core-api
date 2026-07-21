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
