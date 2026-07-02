from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from prisma.enums import Role

from app.database import get_db
from app.deps import get_current_user
from app.models.therapist import (
    TherapistCreate,
    TherapistListResponse,
    TherapistResponse,
    TherapistUpdate,
)
from app.services.therapist import (
    create_therapist,
    delete_therapist,
    get_therapist,
    get_therapist_by_user,
    get_therapists,
    update_therapist,
)

router = APIRouter(prefix="/therapists", tags=["Therapists"])


@router.get("", response_model=TherapistListResponse)
async def list_therapists(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Prisma = Depends(get_db),
):
    therapists, total = await get_therapists(db, skip=skip, limit=limit)
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


@router.get("/{therapist_id}", response_model=TherapistResponse)
async def get_therapist_by_id(
    therapist_id: str,
    db: Prisma = Depends(get_db),
):
    therapist = await get_therapist(db, therapist_id)
    if not therapist:
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
    therapist = await get_therapist(db, therapist_id)
    if not therapist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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
    therapist = await get_therapist(db, therapist_id)
    if not therapist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if therapist.userId != current_user.id and current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await delete_therapist(db, therapist_id)
