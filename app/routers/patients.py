from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date, datetime

from prisma import Prisma
from prisma.enums import Role

from app import (
    OnboardingCompleteRequest,
    OnboardingStatusResponse,
    PatientDashboardResponse,
    PatientProfileResponse,
    PatientProfileUpdate,
    ReferralResponse,
    complete_onboarding,
    get_current_user,
    get_db,
    get_my_patients,
    get_onboarding_status,
    get_patient_dashboard,
    get_patient_profile,
    get_patient_referral,
    save_onboarding_progress,
    upsert_patient_profile,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


def _profile_response(profile, user) -> PatientProfileResponse:
    dob_iso = profile.dob.isoformat() if profile.dob else None
    age = None
    if profile.dob:
        today = date.today()
        age = today.year - profile.dob.year - (
            (today.month, today.day) < (profile.dob.month, profile.dob.day)
        )
    return PatientProfileResponse(
        id=profile.id,
        userId=profile.userId,
        name=profile.name,
        phone=profile.phone,
        city=profile.city,
        address=profile.address,
        history=profile.history,
        dob=dob_iso,
        age=age,
        gender=profile.gender,
        condition=user.condition if user else None,
        emergencyName=profile.emergencyName,
        emergencyRelation=profile.emergencyRelation,
        emergencyPhone=profile.emergencyPhone,
        notifEmail=profile.notifEmail,
        notifSms=profile.notifSms,
        createdAt=profile.createdAt.isoformat(),
        updatedAt=profile.updatedAt.isoformat(),
    )


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
    user = await db.user.find_unique(where={"id": current_user.id})
    return _profile_response(profile, user)


@router.put("/me/profile", response_model=PatientProfileResponse)
async def update_profile(
    data: PatientProfileUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    update_dict = data.model_dump(exclude_unset=True)
    if update_dict.get("dob"):
        update_dict["dob"] = datetime.fromisoformat(update_dict["dob"])
    profile = await upsert_patient_profile(db, current_user.id, update_dict)
    user = await db.user.find_unique(where={"id": current_user.id})
    return _profile_response(profile, user)


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


@router.get("/me/onboarding-status")
async def onboarding_status(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    return await get_onboarding_status(db, current_user.id)


@router.post("/me/onboarding")
async def onboarding(
    data: OnboardingCompleteRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    return await complete_onboarding(db, current_user.id, data.model_dump(exclude_unset=True))


@router.post("/me/onboarding/progress")
async def onboarding_progress(
    data: dict,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    step = data.pop("step", "personal")
    await save_onboarding_progress(db, current_user.id, step, data)
    return {"success": True}
