from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    PaginationParams,
    SlotRangeResponse,
    TherapistCreate,
    TherapistDashboardResponse,
    TherapistListResponse,
    TherapistProfileResponse,
    TherapistProfileUpdate,
    TherapistResponse,
    TherapistUpdate,
    create_therapist,
    delete_therapist,
    get_current_user,
    get_db,
    get_or_404,
    get_therapist_by_user,
    get_therapist_dashboard,
    get_therapist_profile,
    get_therapists,
    get_slots_for_range,
    get_optional_user,
    pagination_params,
    update_therapist,
    update_therapist_profile as update_therapist_profile_svc,
)

router = APIRouter(prefix="/therapists", tags=["Therapists"])


@router.get("/me/dashboard", response_model=TherapistDashboardResponse)
async def dashboard(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    data = await get_therapist_dashboard(db, current_user.id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return TherapistDashboardResponse(**data)


@router.get("", response_model=TherapistListResponse)
async def list_therapists(
    search: str | None = None,
    city: str | None = None,
    specialty: str | None = None,
    gender: str | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    db: Prisma = Depends(get_db),
):
    therapists, total = await get_therapists(
        db,
        search=search,
        city=city,
        specialty=specialty,
        gender=gender,
        **pagination,
    )
    return TherapistListResponse(
        therapists=[TherapistResponse.model_validate(t) for t in therapists],
        total=total,
    )


@router.get("/me", response_model=TherapistResponse)
async def my_profile(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    therapist = await get_therapist_by_user(db, current_user.id)
    if not therapist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return TherapistResponse.model_validate(therapist)


@router.get("/me/profile", response_model=TherapistProfileResponse)
async def my_full_profile(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    profile = await get_therapist_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return TherapistProfileResponse(**profile)


@router.put("/me/profile", response_model=TherapistProfileResponse)
async def update_my_profile(
    data: TherapistProfileUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    import logging
    logger = logging.getLogger(__name__)
    
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    try:
        logger.warning(f"Updating therapist profile for user {current_user.id}, data: {data.model_dump(exclude_none=True)}")
        profile = await update_therapist_profile_svc(
            db, current_user.id, data.model_dump(exclude_none=True)
        )
        logger.warning(f"Profile after update: {profile}")
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return TherapistProfileResponse(**profile)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating therapist profile for user {current_user.id}: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


@router.get("/{therapist_id}/slots", response_model=SlotRangeResponse)
async def get_therapist_slots(
    therapist_id: str,
    from_date: str,
    to_date: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await get_or_404(db, "therapist", therapist_id)
    return await get_slots_for_range(db, therapist.id, from_date, to_date)


@router.get("/{therapist_id}", response_model=TherapistResponse)
async def get_therapist_by_id(
    therapist_id: str,
    requester=Depends(get_optional_user),
    db: Prisma = Depends(get_db),
):
    therapist = await get_or_404(db, "therapist", therapist_id)
    owner = await db.user.find_unique(where={"id": therapist.userId})
    if not owner or owner.status != "APPROVED":
        # Unverified (under review / suspended / rejected) profiles are hidden
        # from the public — only the owner and admins can fetch them.
        is_owner = requester is not None and requester.id == therapist.userId
        is_admin = requester is not None and requester.role == Role.ADMIN
        if not (is_owner or is_admin):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return TherapistResponse.model_validate(therapist)


@router.post(
    "",
    response_model=TherapistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_therapist_profile(
    data: TherapistCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    existing = await get_therapist_by_user(db, current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Therapist profile already exists",
        )
    therapist = await create_therapist(db, current_user.id, data.model_dump())
    return TherapistResponse.model_validate(therapist)


@router.put("/{therapist_id}", response_model=TherapistResponse)
async def update_therapist_profile(
    therapist_id: str,
    data: TherapistUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await get_or_404(db, "therapist", therapist_id)
    if therapist.userId != current_user.id and current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updated = await update_therapist(
        db, therapist_id, data.model_dump(exclude_none=True)
    )
    return TherapistResponse.model_validate(updated)


@router.delete("/{therapist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_therapist_profile(
    therapist_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await get_or_404(db, "therapist", therapist_id)
    if therapist.userId != current_user.id and current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await delete_therapist(db, therapist_id)
