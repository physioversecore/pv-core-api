from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    PatientDashboardResponse,
    PatientProfileResponse,
    PatientProfileUpdate,
    ReferralResponse,
    get_current_user,
    get_db,
    get_my_patients,
    get_patient_dashboard,
    get_patient_profile,
    get_patient_referral,
    upsert_patient_profile,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/me/profile", response_model=PatientProfileResponse)
async def get_profile(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    profile = await get_patient_profile(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )
    return PatientProfileResponse(
        id=profile.id,
        userId=profile.userId,
        name=profile.name,
        phone=profile.phone,
        city=profile.city,
        address=profile.address,
        history=profile.history,
        gender=profile.gender,
        notifEmail=profile.notifEmail,
        notifSms=profile.notifSms,
        createdAt=profile.createdAt.isoformat(),
        updatedAt=profile.updatedAt.isoformat(),
    )


@router.put("/me/profile", response_model=PatientProfileResponse)
async def update_profile(
    data: PatientProfileUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    update_dict = data.model_dump(exclude_unset=True)
    profile = await upsert_patient_profile(db, current_user.id, update_dict)
    return PatientProfileResponse(
        id=profile.id,
        userId=profile.userId,
        name=profile.name,
        phone=profile.phone,
        city=profile.city,
        address=profile.address,
        history=profile.history,
        gender=profile.gender,
        notifEmail=profile.notifEmail,
        notifSms=profile.notifSms,
        createdAt=profile.createdAt.isoformat(),
        updatedAt=profile.updatedAt.isoformat(),
    )


@router.get("/me/dashboard", response_model=PatientDashboardResponse)
async def dashboard(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    data = await get_patient_dashboard(db, current_user.id)
    return PatientDashboardResponse(**data)


@router.get("/me/referral", response_model=ReferralResponse)
async def referral(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    data = await get_patient_referral(db, current_user.id)
    return ReferralResponse(**data)


@router.get("/my-patients")
async def my_patients(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
    search: str | None = Query(default=None),
    condition: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=403, detail="Therapist access required")
    return await get_my_patients(
        db, current_user.id, search=search, condition=condition, skip=skip, limit=limit
    )
