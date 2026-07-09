from fastapi import APIRouter, Depends
from prisma import Prisma
from prisma.enums import Role

from app import (
    PatientDashboardResponse,
    ReferralResponse,
    get_current_user,
    get_db,
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
