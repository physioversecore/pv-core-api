import secrets
import string
from datetime import datetime, timezone

from prisma import Prisma


def generate_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(8))
    return f"SAHA-{suffix}"


async def get_patient_profile(db: Prisma, user_id: str):
    profile = await db.patientprofile.find_unique(where={"userId": user_id})
    return profile


async def upsert_patient_profile(db: Prisma, user_id: str, data: dict):
    existing = await db.patientprofile.find_unique(where={"userId": user_id})
    
    if existing:
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return existing
        profile = await db.patientprofile.update(
            where={"userId": user_id},
            data=update_data,
        )
    else:
        user = await db.user.find_unique(where={"id": user_id})
        filtered = {k: v for k, v in data.items() if v is not None}
        create_data = {
            "userId": user_id,
            "name": filtered.get("name") or (user.name if user else "Patient"),
            "phone": filtered.get("phone") or (user.phone if user and user.phone else ""),
            "city": filtered.get("city") or (user.city if user and user.city else "Kathmandu"),
        }
        if "address" in filtered:
            create_data["address"] = filtered["address"]
        if "history" in filtered:
            create_data["history"] = filtered["history"]
        if "dob" in filtered:
            create_data["dob"] = filtered["dob"]
        if "gender" in filtered:
            create_data["gender"] = filtered["gender"]
        if "emergencyName" in filtered:
            create_data["emergencyName"] = filtered["emergencyName"]
        if "emergencyRelation" in filtered:
            create_data["emergencyRelation"] = filtered["emergencyRelation"]
        if "emergencyPhone" in filtered:
            create_data["emergencyPhone"] = filtered["emergencyPhone"]
        if "notifEmail" in filtered:
            create_data["notifEmail"] = filtered["notifEmail"]
        if "notifSms" in filtered:
            create_data["notifSms"] = filtered["notifSms"]
        profile = await db.patientprofile.create(data=create_data)
    
    return profile


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

    now = datetime.now(timezone.utc)

    sessions = await db.session.find_many(
        where={"patientId": user_id, "status": "SCHEDULED"},
        order={"date": "asc"},
    )

    next_session = None
    for session in sessions:
        try:
            hours, minutes = (int(part) for part in session.time.split(":")[:2])
        except (ValueError, AttributeError):
            continue
        session_dt = session.date
        if session_dt.tzinfo is None:
            session_dt = session_dt.replace(tzinfo=timezone.utc)
        session_dt = session_dt.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        if session_dt <= now:
            continue
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
        break

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


async def get_my_patients(
    db: Prisma,
    therapist_user_id: str,
    *,
    search: str | None = None,
    condition: str | None = None,
    skip: int = 0,
    limit: int = 10,
):
    from datetime import timezone

    therapist = await db.therapist.find_unique(where={"userId": therapist_user_id})
    if not therapist:
        return {"patients": [], "total": 0}

    sessions = await db.session.find_many(
        where={"therapistId": therapist.id},
        order={"date": "desc"},
    )

    patient_map: dict[str, dict] = {}
    for s in sessions:
        pid = s.patientId
        if pid not in patient_map:
            patient_map[pid] = {
                "id": pid,
                "sessions": 0,
                "last": s.date.isoformat(),
                "notes": s.notes or "",
            }
        patient_map[pid]["sessions"] += 1
        if not patient_map[pid]["notes"] and s.notes:
            patient_map[pid]["notes"] = s.notes

    patient_ids = list(patient_map.keys())
    if not patient_ids:
        return {"patients": [], "total": 0}

    where: dict = {"id": {"in": patient_ids}}
    filters: list[dict] = []
    if search:
        filters.append({"name": {"contains": search, "mode": "insensitive"}})
    if condition:
        filters.append({"condition": {"equals": condition, "mode": "insensitive"}})
    if len(filters) == 1:
        where.update(filters[0])
    elif filters:
        where["AND"] = filters

    total = await db.user.count(where=where)
    users = await db.user.find_many(
        where=where,
        order={"name": "asc"},
        skip=skip,
        take=limit,
    )

    result = []
    for u in users:
        meta = patient_map.get(u.id, {})
        last_val = meta.get("last", "")
        if hasattr(last_val, "isoformat"):
            if last_val.tzinfo is None:
                last_val = last_val.replace(tzinfo=timezone.utc)
            last_val = last_val.isoformat()
        result.append({
            "id": u.id,
            "name": u.name,
            "phone": u.phone or "",
            "condition": u.condition or "",
            "sessions": meta.get("sessions", 0),
            "last": last_val,
            "notes": meta.get("notes", ""),
        })

    return {"patients": result, "total": total}
