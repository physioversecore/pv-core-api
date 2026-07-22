from fastapi import APIRouter, Depends, Query
from prisma import Prisma
from prisma.enums import Role

from app import (
    PatientDashboardResponse,
    ReferralResponse,
    get_current_user,
    get_db,
    get_my_patients,
    get_patient_dashboard,
    get_patient_referral,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


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
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Therapist access required")
    return await get_my_patients(
        db, current_user.id, search=search, condition=condition, skip=skip, limit=limit
    )
