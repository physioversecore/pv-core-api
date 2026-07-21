from datetime import datetime, timedelta, timezone

from prisma import Prisma


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
