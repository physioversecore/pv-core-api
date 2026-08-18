from prisma import Prisma


async def get_application_status(db: Prisma, user_id: str) -> dict:
    """Get therapist application status with reviewer feedback."""
    therapist = await db.therapist.find_unique(where={"userId": user_id})
    if not therapist:
        return {"status": "INCOMPLETE", "feedback": []}

    feedback_records = await db.therapistapplicationfeedback.find_many(
        where={"therapistId": therapist.id},
        order={"createdAt": "desc"},
    )

    return {
        "status": therapist.applicationStatus.value if hasattr(therapist.applicationStatus, 'value') else str(therapist.applicationStatus),
        "feedback": [
            {"section": f.section, "message": f.message}
            for f in feedback_records
        ],
    }


async def get_application_sections(db: Prisma, user_id: str) -> dict:
    """Get the therapist's current application data for resume/edit."""
    therapist = await db.therapist.find_unique(where={"userId": user_id})
    user = await db.user.find_unique(where={"id": user_id})

    if not therapist:
        return {
            "personal": {
                "name": user.name if user else "",
                "phone": user.phone or "",
                "city": user.city or "",
                "gender": "",
            },
            "professional": {
                "specialty": "",
                "experience": 0,
                "fee": 0,
                "license": "",
                "bio": "",
            },
            "documents": [],
        }

    verifications = await db.verification.find_many(
        where={"therapistId": therapist.id},
    )

    return {
        "personal": {
            "name": therapist.name,
            "phone": user.phone if user else "",
            "city": therapist.city,
            "gender": therapist.gender,
        },
        "professional": {
            "specialty": therapist.specialty,
            "experience": therapist.experience,
            "fee": therapist.price,
            "license": therapist.licenseNumber or "",
            "bio": therapist.bio,
        },
        "documents": [
            {
                "id": v.id,
                "documentType": v.documentType,
                "documentUrl": v.documentUrl,
                "fileName": v.fileName,
                "status": v.status,
            }
            for v in verifications
        ],
    }


async def update_therapist_application(db: Prisma, user_id: str, data: dict) -> dict:
    """Update therapist application data (for CHANGES_REQUIRED resume)."""
    therapist = await db.therapist.find_unique(where={"userId": user_id})
    if not therapist:
        return {"success": False, "error": "No application found"}

    # Update therapist profile fields
    update_data = {}
    personal = data.get("personal", {})
    professional = data.get("professional", {})

    if personal.get("name"):
        update_data["name"] = personal["name"]
    if personal.get("city"):
        update_data["city"] = personal["city"]
    if personal.get("gender"):
        update_data["gender"] = personal["gender"]
    if professional.get("specialty"):
        update_data["specialty"] = professional["specialty"]
    if professional.get("experience") is not None:
        update_data["experience"] = professional["experience"]
    if professional.get("fee") is not None:
        update_data["price"] = professional["fee"]
    if professional.get("license"):
        update_data["licenseNumber"] = professional["license"]
    if professional.get("bio"):
        update_data["bio"] = professional["bio"]

    if update_data:
        await db.therapist.update(where={"id": therapist.id}, data=update_data)

    # Update user fields
    user_update = {}
    if personal.get("phone"):
        user_update["phone"] = personal["phone"]
    if user_update:
        await db.user.update(where={"id": user_id}, data=user_update)

    # Reset application status to SUBMITTED
    await db.therapist.update(
        where={"id": therapist.id},
        data={"applicationStatus": "SUBMITTED"},
    )

    return {"success": True}
