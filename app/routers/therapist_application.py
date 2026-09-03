from fastapi import APIRouter, Depends, HTTPException, status

from prisma import Prisma

from app import (
    ApplicationStatusResponse,
    get_application_sections,
    get_application_status,
    get_db,
    get_therapist_user,
    update_therapist_application,
)

router = APIRouter(prefix="/therapists", tags=["Therapists"])


@router.get("/me/application-status")
async def therapist_application_status(
    current_user=Depends(get_therapist_user),
    db: Prisma = Depends(get_db),
):
    return await get_application_status(db, current_user.id)


@router.get("/me/application-sections")
async def therapist_application_sections(
    current_user=Depends(get_therapist_user),
    db: Prisma = Depends(get_db),
):
    return await get_application_sections(db, current_user.id)


@router.put("/me/application")
async def update_application(
    data: dict,
    current_user=Depends(get_therapist_user),
    db: Prisma = Depends(get_db),
):
    result = await update_therapist_application(db, current_user.id, data)
    if result.get("success"):
        from app.services.notification import log_admin_notification
        therapist = await db.therapist.find_unique(where={"userId": current_user.id})
        await log_admin_notification(
            db,
            category="therapist",
            message=f"New therapist application submitted by **{current_user.name}**",
            action_type="therapist",
            action_id=therapist.id if therapist else current_user.id,
        )
    return result
