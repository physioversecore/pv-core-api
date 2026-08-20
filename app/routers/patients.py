from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date, datetime

from prisma import Prisma
from prisma.enums import Role

from app import (
    FamilyMemberCreate,
    FamilyMemberUpdate,
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
        photo=profile.photo,
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


# ─── Family Members ──────────────────────────────────────────────────────────

async def _get_patient_profile_or_404(db: Prisma, user_id: str):
    profile = await db.patientprofile.find_unique(where={"userId": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return profile


@router.get("/me/family-members")
async def list_family_members(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    profile = await _get_patient_profile_or_404(db, current_user.id)
    members = await db.familymember.find_many(
        where={"patientId": profile.id},
        order={"createdAt": "asc"},
    )
    return [
        {
            "id": m.id,
            "name": m.name,
            "relationship": m.relationship,
            "dob": m.dob.isoformat() if m.dob else None,
            "phone": m.phone,
            "gender": m.gender,
            "condition": m.condition,
        }
        for m in members
    ]


@router.post("/me/family-members")
async def add_family_member(
    data: FamilyMemberCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    profile = await _get_patient_profile_or_404(db, current_user.id)
    dob_dt = None
    if data.dob:
        try:
            dob_dt = datetime.fromisoformat(data.dob)
        except ValueError:
            pass
    member = await db.familymember.create(
        data={
            "patientId": profile.id,
            "name": data.name,
            "relationship": data.relationship,
            "dob": dob_dt,
            "phone": data.phone,
            "gender": data.gender,
            "condition": data.condition,
        }
    )
    return {
        "id": member.id,
        "name": member.name,
        "relationship": member.relationship,
        "dob": member.dob.isoformat() if member.dob else None,
        "phone": member.phone,
        "gender": member.gender,
        "condition": member.condition,
    }


@router.put("/me/family-members/{member_id}")
async def update_family_member(
    member_id: str,
    data: FamilyMemberUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    profile = await _get_patient_profile_or_404(db, current_user.id)
    member = await db.familymember.find_unique(where={"id": member_id})
    if not member or member.patientId != profile.id:
        raise HTTPException(status_code=404, detail="Family member not found")

    update_data = data.model_dump(exclude_unset=True)
    if "dob" in update_data and update_data["dob"]:
        try:
            update_data["dob"] = datetime.fromisoformat(update_data["dob"])
        except ValueError:
            update_data.pop("dob")
    elif "dob" in update_data and update_data["dob"] is None:
        update_data["dob"] = None

    member = await db.familymember.update(where={"id": member_id}, data=update_data)
    return {
        "id": member.id,
        "name": member.name,
        "relationship": member.relationship,
        "dob": member.dob.isoformat() if member.dob else None,
        "phone": member.phone,
        "gender": member.gender,
        "condition": member.condition,
    }


@router.delete("/me/family-members/{member_id}")
async def delete_family_member(
    member_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    profile = await _get_patient_profile_or_404(db, current_user.id)
    member = await db.familymember.find_unique(where={"id": member_id})
    if not member or member.patientId != profile.id:
        raise HTTPException(status_code=404, detail="Family member not found")

    await db.familymember.delete(where={"id": member_id})
    return {"success": True}
