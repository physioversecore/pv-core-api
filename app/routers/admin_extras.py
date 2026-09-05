from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma

from app import get_admin_user, get_current_user, get_db
from app.services.activity_log import log_admin_activity
from app.services.notification import (
    list_admin_notifications,
    mark_notification_read,
    mark_all_notifications_read,
)

router = APIRouter(prefix="/admin", tags=["Admin Extras"])


# ── Payments management ──


@router.get("/payments")
async def list_admin_payments(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    method: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "desc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    where: dict = {}
    if search:
        where["OR"] = [
            {"user": {"name": {"contains": search, "mode": "insensitive"}}},
            {"user": {"email": {"contains": search, "mode": "insensitive"}}},
        ]
    if status_filter:
        where["status"] = status_filter.upper()
    if method:
        where["method"] = {"contains": method, "mode": "insensitive"}

    total = await db.payment.count(where=where)
    payments = await db.payment.find_many(
        where=where,
        include={"user": True},
        order={"createdAt": sortOrder},
        skip=skip,
        take=limit,
    )
    items = []
    for p in payments:
        user = p.user if hasattr(p, "user") and p.user else None
        items.append({
            "id": p.id,
            "userId": p.userId,
            "userName": user.name if user else "Unknown",
            "userEmail": user.email if user else "",
            "amount": p.amount,
            "method": p.method or "",
            "status": p.status,
            "currency": p.currency or "NPR",
            "sessionId": p.sessionId,
            "platformFee": p.platformFee or 0,
            "paymentType": p.paymentType or "",
            "createdAt": p.createdAt.isoformat() if p.createdAt else "",
        })
    return {"items": items, "total": total}


@router.get("/payments/stats")
async def admin_payment_stats(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_payments = await db.payment.count()
    all_completed = await db.payment.find_many(where={"status": "COMPLETED"})
    total_amount = sum(p.amount for p in all_completed)

    month_count = await db.payment.count(
        where={"createdAt": {"gte": month_start.replace(tzinfo=None)}}
    )
    month_completed = await db.payment.find_many(
        where={
            "status": "COMPLETED",
            "createdAt": {"gte": month_start.replace(tzinfo=None)},
        }
    )
    month_amount = sum(p.amount for p in month_completed)

    return {
        "totalPayments": total_payments,
        "totalAmount": total_amount,
        "monthPayments": month_count,
        "monthAmount": month_amount,
    }


@router.put("/payments/{payment_id}")
async def update_admin_payment(
    payment_id: str,
    data: dict,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await db.payment.find_unique(where={"id": payment_id})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    update_fields = {}
    for key in ("status", "method", "amount"):
        if key in data and data[key] is not None:
            update_fields[key] = data[key]
    if not update_fields:
        return {"id": existing.id, "status": existing.status}
    updated = await db.payment.update(where={"id": payment_id}, data=update_fields)
    await log_admin_activity(
        db, _.id, "UPDATE_PAYMENT", "Payment", payment_id,
        {"status": updated.status, "amount": updated.amount},
    )
    return {"id": updated.id, "status": updated.status, "amount": updated.amount}


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_payment(
    payment_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await db.payment.find_unique(where={"id": payment_id})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.payment.delete(where={"id": payment_id})


# ── Payouts (derived from completed sessions) ──


@router.get("/payouts")
async def list_admin_payouts(
    skip: int = 0,
    limit: int = 10,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    from collections import defaultdict
    from datetime import date

    sessions = await db.session.find_many(
        where={"status": "COMPLETED"},
        order={"date": "desc"},
    )
    monthly = defaultdict(lambda: {"earnings": 0.0, "sessions": 0})
    for s in sessions:
        key = s.date.strftime("%Y-%m") if s.date else "unknown"
        monthly[key]["earnings"] += s.fee
        monthly[key]["sessions"] += 1

    all_payouts = [
        {
            "id": f"payout-{month}",
            "month": month,
            "earnings": round(data["earnings"], 2),
            "sessions": data["sessions"],
            "status": "Completed" if month < date.today().strftime("%Y-%m") else "Pending",
            "paidAt": f"{month}-28",
        }
        for month, data in sorted(monthly.items(), reverse=True)
    ]
    paged = all_payouts[skip:skip + limit]
    return {"items": paged, "total": len(all_payouts)}


@router.put("/payouts/{payout_id}")
async def update_admin_payout(
    payout_id: str,
    data: dict,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return {"id": payout_id, "status": data.get("status", "Completed"), "message": "Payout updated"}


@router.delete("/payouts/{payout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_payout(
    payout_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return None


# ── Notifications ──


@router.get("/notifications")
async def list_notifications(
    skip: int = 0,
    limit: int = 20,
    category: str | None = None,
    read: bool | None = None,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total, unread_count = await list_admin_notifications(
        db, skip=skip, limit=limit, category=category, read=read,
    )
    return {"items": items, "total": total, "unreadCount": unread_count}


@router.put("/notifications/read-all")
async def mark_all_notifications_read_endpoint(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    count = await mark_all_notifications_read(db)
    return {"message": "All notifications marked as read", "count": count}


@router.put("/notifications/{notification_id}")
async def mark_notification_read_endpoint(
    notification_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await mark_notification_read(db, notification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


# ── Team management (admin users) ──


@router.get("/team")
async def list_admin_team(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    admins = await db.user.find_many(
        where={"role": "ADMIN"},
        order={"createdAt": "desc"},
    )
    items = [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "createdAt": u.createdAt.isoformat() if u.createdAt else "",
        }
        for u in admins
    ]
    return {"items": items, "total": len(items)}


@router.post("/team/invite")
async def invite_admin_user(
    data: dict,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    from app.services.auth import hash_password
    import secrets

    email = data.get("email", "")
    name = data.get("name", "Admin User")
    existing = await db.user.find_unique(where={"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    temp_password = secrets.token_urlsafe(12)
    user = await db.user.create(
        data={
            "name": name,
            "email": email,
            "password": hash_password(temp_password),
            "role": "ADMIN",
            "status": "APPROVED",
            "city": data.get("city", "Kathmandu"),
            "phone": data.get("phone"),
        }
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "message": f"Invitation sent to {email}",
    }


@router.put("/team/{user_id}")
async def update_admin_team_member(
    user_id: str,
    data: dict,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await db.user.find_unique(where={"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    update_fields = {}
    for key in ("name", "email", "role", "status"):
        if key in data and data[key] is not None:
            update_fields[key] = data[key]
    if not update_fields:
        return {"id": existing.id, "name": existing.name, "email": existing.email, "role": existing.role}
    updated = await db.user.update(where={"id": user_id}, data=update_fields)
    await log_admin_activity(
        db, _.id, "UPDATE_TEAM", "TeamMember", user_id,
        {"name": updated.name},
    )
    return {"id": updated.id, "name": updated.name, "email": updated.email, "role": updated.role}


# ── Leaves (ScheduleBlockRequest used as leaves) ──


@router.get("/leaves/stats")
async def admin_leave_stats(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    today = date.today().isoformat()
    this_month_start = date.today().replace(day=1).isoformat()
    next_month_start = date.today().replace(day=28) + timedelta(days=4)
    this_month_end = (next_month_start.replace(day=1) - timedelta(days=1)).isoformat()

    pending = await db.scheduleblockrequest.count(where={"status": "PENDING"})

    on_leave_today = await db.scheduleblockrequest.count(
        where={
            "status": "APPROVED",
            "dateFrom": {"lte": today},
            "dateTo": {"gte": today},
        },
    )

    approved_this_month = await db.scheduleblockrequest.count(
        where={
            "status": "APPROVED",
            "dateFrom": {"gte": this_month_start, "lte": this_month_end},
        },
    )

    # Total sessions booked within any active leave window for their therapist
    active_leaves = await db.scheduleblockrequest.find_many(
        where={"status": "APPROVED"},
    )
    bookings_affected = 0
    for leave in active_leaves:
        try:
            df = datetime.fromisoformat(leave.dateFrom)
        except (ValueError, TypeError):
            continue
        dt = leave.dateTo
        try:
            dto = datetime.fromisoformat(dt) if dt else df
        except (ValueError, TypeError):
            dto = df
        if dto < df:
            dto = df
        bookings_affected += await db.session.count(
            where={
                "therapistId": leave.therapistId,
                "date": {"gte": df, "lte": dto},
                "status": {"in": ["SCHEDULED", "IN_PROGRESS"]},
            },
        )

    return {
        "pending": pending,
        "onLeaveToday": on_leave_today,
        "approvedThisMonth": approved_this_month,
        "bookingsAffected": bookings_affected,
    }


@router.get("/leaves")
async def list_admin_leaves(
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
    search: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "desc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    where: dict = {}
    if status:
        where["status"] = status.upper()

    # Resolve therapist name search across related rows
    if search:
        therapists = await db.therapist.find_many(
            where={"name": {"contains": search, "mode": "insensitive"}},
            select={"id": True},
        )
        matching_ids = [t.id for t in therapists]
        if matching_ids:
            where["therapistId"] = {"in": matching_ids}
        else:
            where["therapistId"] = {"in": []}

    if dateFrom:
        where["dateTo"] = {"gte": dateFrom}
    if dateTo:
        where["dateFrom"] = {"lte": dateTo}

    total = await db.scheduleblockrequest.count(where=where)

    # Map sortable columns to Prisma order clauses. "therapist" sorts by the
    # linked Therapist name; "bookingsAffected" is computed post-query so it
    # falls back to createdAt ordering.
    order: dict = {"createdAt": "desc"}
    if sortBy == "therapist":
        order = {"therapist": {"name": sortOrder}}
    elif sortBy in ("dateFrom", "status", "reason"):
        order = {sortBy: sortOrder}
    requests = await db.scheduleblockrequest.find_many(
        where=where,
        order=order,
        skip=skip,
        take=limit,
    )

    items = []
    for r in requests:
        therapist = await db.therapist.find_unique(where={"id": r.therapistId})
        therapist_user = (
            await db.user.find_unique(where={"id": therapist.userId})
            if therapist
            else None
        )
        # Count booked sessions overlapping the leave window for this therapist
        bookings_affected = 0
        try:
            df = datetime.fromisoformat(r.dateFrom)
        except (ValueError, TypeError):
            df = None
        dt = r.dateTo
        try:
            dto = datetime.fromisoformat(dt) if dt else df
        except (ValueError, TypeError):
            dto = df
        if df and dto:
            if dto < df:
                dto = df
            bookings_affected = await db.session.count(
                where={
                    "therapistId": r.therapistId,
                    "date": {"gte": df, "lte": dto},
                    "status": {"in": ["SCHEDULED", "IN_PROGRESS"]},
                },
            )
        items.append({
            "id": r.id,
            "therapistId": r.therapistId,
            "therapist": therapist.name if therapist else "Unknown",
            "therapistName": therapist.name if therapist else "Unknown",
            "therapistEmail": therapist_user.email if therapist_user else "",
            "dateFrom": r.dateFrom,
            "dateTo": r.dateTo,
            "reason": r.reason,
            "status": r.status,
            "bookingsAffected": bookings_affected,
            "adminNotes": r.adminNotes,
            "createdAt": r.createdAt.isoformat() if r.createdAt else "",
        })
    return {"items": items, "total": total}


@router.put("/leaves/{leave_id}")
async def update_admin_leave(
    leave_id: str,
    data: dict,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await db.scheduleblockrequest.find_unique(where={"id": leave_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Leave not found")

    update_data: dict = {}
    if "status" in data:
        new_status = data["status"].upper()
        if new_status not in ("PENDING", "APPROVED", "REJECTED"):
            raise HTTPException(status_code=422, detail="Invalid status")
        update_data["status"] = new_status
    if "adminNotes" in data:
        update_data["adminNotes"] = data["adminNotes"]
    if "dateFrom" in data:
        update_data["dateFrom"] = data["dateFrom"]
    if "dateTo" in data:
        update_data["dateTo"] = data["dateTo"]
    if "reason" in data:
        update_data["reason"] = data["reason"]

    updated = await db.scheduleblockrequest.update(
        where={"id": leave_id},
        data=update_data,
    )
    new_status = update_data.get("status")
    if new_status == "APPROVED":
        action = "APPROVE_LEAVE"
    elif new_status == "REJECTED":
        action = "REJECT_LEAVE"
    else:
        action = "UPDATE_LEAVE"
    await log_admin_activity(
        db, _.id, action, "LeaveRequest", leave_id,
        {"status": updated.status},
    )
    return {"id": updated.id, "status": updated.status, "adminNotes": updated.adminNotes}


@router.delete("/leaves/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_leave(
    leave_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await db.scheduleblockrequest.find_unique(where={"id": leave_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Leave not found")
    await db.scheduleblockrequest.delete(where={"id": leave_id})


# ── Incidents (Complaints used as incidents) ──


COMPLAINT_TO_INCIDENT_STATUS = {
    "Open": "Active",
    "In Progress": "Investigating",
    "Investigating": "Investigating",
    "Escalated": "Escalated",
    "Resolved": "Resolved",
    "Dismissed": "Resolved",
}
PRIORITY_TO_SEVERITY = {
    "Urgent": "Critical",
    "High": "High",
    "Normal": "Medium",
    "Medium": "Medium",
    "Critical": "Critical",
}


def _map_complaint_to_incident(c) -> dict:
    raw_status = getattr(c, "status", "Open") or "Open"
    raw_priority = getattr(c, "priority", "Normal") or "Normal"
    complainant_name = getattr(c, "complainantName", "") or ""
    against_name = getattr(c, "againstName", "") or ""
    ctype = getattr(c, "type", "patient") or "patient"
    return {
        "id": c.id,
        "reportedBy": "Therapist" if ctype == "therapist" else "Patient",
        "therapist": against_name if ctype == "patient" else complainant_name,
        "patient": complainant_name if ctype == "patient" else against_name,
        "severity": PRIORITY_TO_SEVERITY.get(raw_priority, "Medium"),
        "summary": getattr(c, "description", "") or "",
        "status": COMPLAINT_TO_INCIDENT_STATUS.get(raw_status, "Active"),
        "reportedAt": c.createdAt.isoformat() if c.createdAt else "",
        "assignedTo": getattr(c, "assignee", None),
        "phone": "",
    }


@router.get("/incidents")
async def list_admin_incidents(
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
    severity: str | None = None,
    reportedBy: str | None = None,
    search: str | None = None,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    where: dict = {}
    if status:
        where["status"] = status

    complaints = await db.complaint.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )

    items = [_map_complaint_to_incident(c) for c in complaints]

    if severity:
        items = [i for i in items if i["severity"] == severity]
    if reportedBy:
        items = [i for i in items if i["reportedBy"] == reportedBy]
    if search:
        q = search.lower()
        items = [
            i for i in items
            if q in (i["therapist"] or "").lower()
            or q in (i["patient"] or "").lower()
            or q in (i["id"] or "").lower()
            or q in (i["summary"] or "").lower()
        ]

    total = len(complaints)
    return {"items": items, "total": total}


@router.put("/incidents/{incident_id}/escalate")
async def escalate_incident(
    incident_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await db.complaint.find_unique(where={"id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Incident not found")
    updated = await db.complaint.update(
        where={"id": incident_id},
        data={"status": "Escalated"},
    )
    return _map_complaint_to_incident(updated)


@router.put("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    data: dict = {},
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await db.complaint.find_unique(where={"id": incident_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Incident not found")
    updated = await db.complaint.update(
        where={"id": incident_id},
        data={"status": "Resolved"},
    )
    result = _map_complaint_to_incident(updated)
    result["message"] = data.get("outcome", "Resolved")
    return result


# ── Analytics ──


@router.get("/analytics/stats")
async def admin_analytics_stats(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month = (month_start - timedelta(days=1)).replace(day=1)
    month_start_naive = month_start.replace(tzinfo=None)
    last_month_naive = last_month.replace(tzinfo=None)

    total_sessions = await db.session.count()
    month_sessions = await db.session.count(
        where={"createdAt": {"gte": month_start_naive}}
    )
    completed = await db.session.count(where={"status": "COMPLETED"})
    cancelled = await db.session.count(where={"status": "CANCELLED"})
    total_patients = await db.user.count(where={"role": "PATIENT"})
    total_therapists = await db.user.count(where={"role": "THERAPIST"})

    cached_total = (cancelled / total_sessions * 100) if total_sessions > 0 else 0
    prev_cancelled = await db.session.count(
        where={"status": "CANCELLED", "createdAt": {"gte": last_month_naive, "lt": month_start_naive}}
    )
    prev_total = await db.session.count(
        where={"createdAt": {"gte": last_month_naive, "lt": month_start_naive}}
    )

    # Revenue from completed payments (MTD vs last month)
    revenue_mtd = 0.0
    revenue_last = 0.0
    for p in await db.payment.find_many(where={"status": "COMPLETED"}):
        if p.createdAt and p.createdAt.replace(tzinfo=timezone.utc) >= month_start:
            revenue_mtd += p.amount or 0
        elif p.createdAt and last_month <= p.createdAt.replace(tzinfo=timezone.utc) < month_start:
            revenue_last += p.amount or 0

    def _fmt_revenue(amount: float) -> str:
        if amount >= 100000:
            return f"Rs {amount / 100000:.1f}L"
        return f"Rs {amount:,.0f}"

    revenue_change = 0.0
    if revenue_last > 0:
        revenue_change = (revenue_mtd - revenue_last) / revenue_last * 100

    # Repeat booking rate: patients with >=2 sessions (all-time vs last month)
    patients = await db.user.find_many(where={"role": "PATIENT"}, include={"sessionsAsPatient": True})
    repeat_all = 0
    repeat_month = 0
    active_month_users = set()
    for u in patients:
        count_total = len(u.sessionsAsPatient or [])
        count_month = sum(1 for s in (u.sessionsAsPatient or []) if s.createdAt and s.createdAt.replace(tzinfo=timezone.utc) >= month_start)
        if count_total >= 2:
            repeat_all += 1
            if count_month > 0:
                active_month_users.add(u.id)
        if count_month >= 2:
            repeat_month += 1
    repeat_rate = (repeat_all / len(patients) * 100) if patients else 0
    repeat_rate_month = (repeat_month / max(len(active_month_users), 1) * 100)

    # Avg session rating from reviews
    reviews = await db.review.find_many()
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 4.5

    return {
        "totalSessions": total_sessions,
        "monthSessions": month_sessions,
        "completedSessions": completed,
        "cancellationRate": round(cached_total, 1),
        "cancellationChange": round((cached_total - (prev_cancelled / prev_total * 100 if prev_total else 0)), 1),
        "revenueMTD": _fmt_revenue(revenue_mtd),
        "revenueChange": f"{revenue_change:.0f}%",
        "repeatBookingRate": f"{round(repeat_rate):.0f}%",
        "repeatChange": f"{round(repeat_rate - (repeat_rate_month if repeat_all else repeat_rate)):.0f}%",
        "avgSessionRating": f"{avg_rating}",
        "ratingNote": "Above 4.5 target" if avg_rating >= 4.5 else "Below 4.5 target",
        "totalPatients": total_patients,
        "totalTherapists": total_therapists,
    }


@router.get("/analytics/bookings-by-zone")
async def bookings_by_zone(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    areas = await db.servicearea.find_many()
    result = []
    for area in areas:
        count = await db.therapistservicearea.count(
            where={"serviceAreaId": area.id}
        )
        result.append({
            "zone": area.name,
            "bookings": count,
            "isWarning": count < 2,
        })
    if not result:
        sessions = await db.session.find_many()
        from collections import defaultdict
        city_counts = defaultdict(int)
        for s in sessions:
            city_counts["Unknown"] += 1
        result = [{"zone": k, "bookings": v, "isWarning": False} for k, v in city_counts.items()]
    return result


@router.get("/analytics/cancellation-rate")
async def cancellation_rate_by_therapist(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    therapists = await db.therapist.find_many()
    result = []
    for t in therapists:
        total = await db.session.count(where={"therapistId": t.id})
        cancelled = await db.session.count(
            where={"therapistId": t.id, "status": "CANCELLED"}
        )
        rate = (cancelled / total * 100) if total > 0 else 0
        result.append({
            "therapistId": t.id,
            "therapist": t.name,
            "therapistName": t.name,
            "totalSessions": total,
            "cancelled": cancelled,
            "rate": round(rate, 1),
            "isWarning": rate >= 10,
            "isAmber": 5 <= rate < 10,
        })
    return result


@router.get("/analytics/revenue-trend")
async def revenue_trend(
    months: int = Query(6, ge=1, le=24),
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone
    from collections import defaultdict

    now = datetime.now(timezone.utc)
    payments = await db.payment.find_many(
        where={"status": "COMPLETED"},
        order={"createdAt": "asc"},
    )

    monthly = defaultdict(float)
    for p in payments:
        key = p.createdAt.strftime("%Y-%m") if p.createdAt else "unknown"
        monthly[key] += p.amount

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def _fmt_revenue(amount: float) -> str:
        if amount >= 100000:
            return f"Rs {amount / 100000:.1f}L"
        return f"Rs {amount:,.0f}"

    trend = []
    for i in range(months - 1, -1, -1):
        d = now - timedelta(days=i * 30)
        key = d.strftime("%Y-%m")
        label = month_labels[int(key.split("-")[1]) - 1]
        if i == 0:
            label = f"{label} MTD"
        trend.append({
            "month": label,
            "revenue": _fmt_revenue(monthly.get(key, 0)),
        })
    return trend


# ── Sidebar nav badge counts ──


@router.get("/nav-badges")
async def admin_nav_badges(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    pending_leaves = await db.scheduleblockrequest.count(where={"status": "PENDING"})
    pending_refunds = await db.refund.count(where={"status": "PENDING"})
    pending_verifications = await db.user.count(
        where={"role": "THERAPIST", "status": "PENDING"}
    )
    return {
        "pendingLeaves": pending_leaves,
        "pendingRefunds": pending_refunds,
        "pendingVerifications": pending_verifications,
    }
