from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma

from app import get_admin_user, get_current_user, get_db

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
async def list_admin_notifications(
    skip: int = 0,
    limit: int = 20,
    unread_only: bool = False,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    sessions = await db.session.find_many(
        order={"createdAt": "desc"},
        take=limit,
        include={"therapist": True, "patient": True},
    )
    notifications = []
    for i, s in enumerate(sessions):
        patient = s.patient if hasattr(s, "patient") and s.patient else None
        therapist = s.therapist if hasattr(s, "therapist") and s.therapist else None
        notif_type = {
            "SCHEDULED": "new_booking",
            "COMPLETED": "session_completed",
            "CANCELLED": "session_cancelled",
            "RESCHEDULE_REQUESTED": "reschedule_requested",
        }.get(s.status, "info")
        notifications.append({
            "id": s.id,
            "type": notif_type,
            "message": f"Session {s.status.lower()} with {patient.name if patient else 'Unknown'} by {therapist.name if therapist else 'Unknown'}",
            "read": False,
            "createdAt": s.createdAt.isoformat() if s.createdAt else "",
        })
    return {"items": notifications, "total": len(notifications)}


@router.put("/notifications/{notification_id}")
async def mark_notification_read(
    notification_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return {"id": notification_id, "read": True}


@router.put("/notifications/read-all")
async def mark_all_notifications_read(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return {"message": "All notifications marked as read", "count": 0}


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
    return {"id": updated.id, "name": updated.name, "email": updated.email, "role": updated.role}


# ── Leaves (TherapistServiceArea or AvailabilityBlock used as leaves) ──


@router.get("/leaves")
async def list_admin_leaves(
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    where: dict = {}
    if status:
        where["status"] = status.upper()

    requests = await db.scheduleblockrequest.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit,
    )
    total = await db.scheduleblockrequest.count(where=where)
    items = []
    for r in requests:
        therapist = await db.therapist.find_unique(where={"id": r.therapistId})
        user = await db.user.find_unique(where={"id": therapist.userId}) if therapist else None
        items.append({
            "id": r.id,
            "therapistId": r.therapistId,
            "therapistName": therapist.name if therapist else "Unknown",
            "therapistEmail": user.email if user else "",
            "dateFrom": r.dateFrom,
            "dateTo": r.dateTo,
            "reason": r.reason,
            "status": r.status,
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
    new_status = data.get("status", existing.status)
    admin_notes = data.get("adminNotes", existing.adminNotes)
    updated = await db.scheduleblockrequest.update(
        where={"id": leave_id},
        data={"status": new_status.upper(), "adminNotes": admin_notes},
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


@router.get("/incidents")
async def list_admin_incidents(
    skip: int = 0,
    limit: int = 10,
    status: str | None = None,
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
    total = await db.complaint.count(where=where)
    items = []
    for c in complaints:
        items.append({
            "id": c.id,
            "type": c.type if hasattr(c, "type") else "general",
            "category": c.category if hasattr(c, "category") else "",
            "description": c.description if hasattr(c, "description") else "",
            "status": c.status,
            "priority": c.priority if hasattr(c, "priority") else "medium",
            "complainantId": c.complainantId if hasattr(c, "complainantId") else "",
            "againstId": c.againstId if hasattr(c, "againstId") else "",
            "createdAt": c.createdAt.isoformat() if c.createdAt else "",
        })
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
    return {"id": updated.id, "status": updated.status}


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
    return {"id": updated.id, "status": updated.status, "message": data.get("outcome", "Resolved")}


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

    total_sessions = await db.session.count()
    month_sessions = await db.session.count(
        where={"createdAt": {"gte": month_start.replace(tzinfo=None)}}
    )
    completed = await db.session.count(where={"status": "COMPLETED"})
    cancelled = await db.session.count(where={"status": "CANCELLED"})
    total_patients = await db.user.count(where={"role": "PATIENT"})
    total_therapists = await db.user.count(where={"role": "THERAPIST"})

    cancellation_rate = (cancelled / total_sessions * 100) if total_sessions > 0 else 0

    return {
        "totalSessions": total_sessions,
        "monthSessions": month_sessions,
        "completedSessions": completed,
        "cancellationRate": round(cancellation_rate, 1),
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
        })
    if not result:
        sessions = await db.session.find_many()
        from collections import defaultdict
        city_counts = defaultdict(int)
        for s in sessions:
            city_counts["Unknown"] += 1
        result = [{"zone": k, "bookings": v} for k, v in city_counts.items()]
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
            "therapistName": t.name,
            "totalSessions": total,
            "cancelled": cancelled,
            "rate": round(rate, 1),
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

    trend = []
    for i in range(months - 1, -1, -1):
        d = now - timedelta(days=i * 30)
        key = d.strftime("%Y-%m")
        trend.append({
            "month": key,
            "revenue": round(monthly.get(key, 0), 2),
        })
    return trend
