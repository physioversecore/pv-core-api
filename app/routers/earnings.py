from fastapi import APIRouter, Depends, Query
from prisma import Prisma
from prisma.enums import Role

from app import get_current_user, get_db, get_therapist_by_user

router = APIRouter(prefix="/therapist", tags=["Therapist Earnings"])


@router.get("/earnings/transactions")
async def get_therapist_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.THERAPIST:
        return {"transactions": [], "total": 0, "page": page, "limit": limit}

    therapist = await get_therapist_by_user(db, current_user.id)
    if not therapist:
        return {"transactions": [], "total": 0, "page": page, "limit": limit}

    skip = (page - 1) * limit
    sessions = await db.session.find_many(
        where={"therapistId": therapist.id},
        order={"date": "desc"},
        skip=skip,
        take=limit,
    )
    total = await db.session.count(where={"therapistId": therapist.id})

    patient_ids = list({s.patientId for s in sessions if s.patientId})
    patients = await db.user.find_many(where={"id": {"in": patient_ids}}) if patient_ids else []
    patient_map = {p.id: p for p in patients}

    session_ids = [s.id for s in sessions]
    payments = await db.payment.find_many(where={"sessionId": {"in": session_ids}}) if session_ids else []
    payment_map = {p.sessionId: p for p in payments}

    transactions = []
    for s in sessions:
        payment = payment_map.get(s.id)
        patient = patient_map.get(s.patientId)
        transactions.append({
            "id": s.id,
            "patientName": patient.name if patient else "Unknown",
            "patientPhone": patient.phone if patient else "",
            "date": s.date.strftime("%Y-%m-%d") if s.date else "",
            "time": s.time or "",
            "type": s.type,
            "fee": s.fee,
            "status": s.status,
            "paymentMethod": payment.method if payment else "",
            "paymentStatus": payment.status if payment else "PENDING",
        })

    return {"transactions": transactions, "total": total, "page": page, "limit": limit}


@router.get("/earnings/payouts")
async def get_therapist_payouts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.THERAPIST:
        return {"payouts": [], "total": 0, "page": page, "limit": limit}

    therapist = await get_therapist_by_user(db, current_user.id)
    if not therapist:
        return {"payouts": [], "total": 0, "page": page, "limit": limit}

    completed_sessions = await db.session.find_many(
        where={"therapistId": therapist.id, "status": "COMPLETED"},
        order={"date": "desc"},
    )

    from collections import defaultdict
    monthly = defaultdict(lambda: {"earnings": 0.0, "sessions": 0})
    for s in completed_sessions:
        key = s.date.strftime("%Y-%m") if s.date else "unknown"
        monthly[key]["earnings"] += s.fee
        monthly[key]["sessions"] += 1

    all_payouts = [
        {
            "id": f"payout-{month}",
            "month": month,
            "earnings": round(data["earnings"], 2),
            "sessions": data["sessions"],
            "status": "Completed" if month < __import__("datetime").date.today().strftime("%Y-%m") else "Pending",
            "paidAt": f"{month}-28",
        }
        for month, data in sorted(monthly.items(), reverse=True)
    ]

    skip = (page - 1) * limit
    paged = all_payouts[skip:skip + limit]
    return {"payouts": paged, "total": len(all_payouts), "page": page, "limit": limit}
