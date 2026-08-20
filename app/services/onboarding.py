from datetime import datetime

from prisma import Prisma


def _parse_dob(val):
    """Convert a date string (YYYY-MM-DD) to a datetime object, or return None."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


async def get_onboarding_status(db: Prisma, user_id: str) -> dict:
    """Get the onboarding status for a patient."""
    profile = await db.patientprofile.find_unique(where={"userId": user_id})
    if not profile:
        return {"completed": False, "step": "personal"}
    if profile.onboardingCompleted:
        return {"completed": True, "step": None}
    return {"completed": False, "step": profile.onboardingStep or "personal"}


async def save_onboarding_progress(db: Prisma, user_id: str, step: str, data: dict):
    """Save partial onboarding progress (called on each step navigation)."""
    existing = await db.patientprofile.find_unique(where={"userId": user_id})

    update_fields: dict = {"onboardingStep": step}

    # Map frontend fields to DB columns
    field_map = {
        "name": "name",
        "phone": "phone",
        "city": "city",
        "address": "address",
        "dob": "dob",
        "gender": "gender",
        "condition": None,  # stored on User model
        "medicalHistory": "history",
        "emergencyName": "emergencyName",
        "emergencyRelation": "emergencyRelation",
        "emergencyPhone": "emergencyPhone",
    }

    db_fields = {}
    user_fields = {}
    for key, val in data.items():
        if val is None:
            continue
        col = field_map.get(key)
        if col is None and key == "condition":
            user_fields["condition"] = val
        elif col:
            db_fields[col] = val

    # Convert dob string to datetime for Prisma
    if "dob" in db_fields:
        db_fields["dob"] = _parse_dob(db_fields["dob"])

    if existing:
        if db_fields:
            update_fields.update(db_fields)
        await db.patientprofile.update(where={"userId": user_id}, data=update_fields)
    else:
        user = await db.user.find_unique(where={"id": user_id})
        create_data = {
            "user": {"connect": {"id": user_id}},
            "name": db_fields.get("name") or (user.name if user else "Patient"),
            "phone": db_fields.get("phone") or (user.phone if user and user.phone else ""),
            "city": db_fields.get("city") or (user.city if user and user.city else "Kathmandu"),
            "onboardingStep": step,
            "onboardingCompleted": False,
        }
        for k in ["address", "history", "dob", "gender", "emergencyName", "emergencyRelation", "emergencyPhone"]:
            if k in db_fields:
                create_data[k] = db_fields[k]
        await db.patientprofile.create(data=create_data)

    if user_fields:
        await db.user.update(where={"id": user_id}, data=user_fields)


async def complete_onboarding(db: Prisma, user_id: str, data: dict):
    """Mark onboarding as completed and save all profile data."""
    # Save all fields first
    await save_onboarding_progress(db, user_id, "review", data)

    # Mark as completed
    await db.patientprofile.update(
        where={"userId": user_id},
        data={"onboardingCompleted": True, "onboardingStep": None},
    )

    # Save condition on User model if provided
    if data.get("condition"):
        await db.user.update(where={"id": user_id}, data={"condition": data["condition"]})

    return {"success": True}
