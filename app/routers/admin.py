from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import UserStatus

from app import (
    PaginationParams,
    UserResponse,
    get_admin_user,
    get_current_user,
    get_db,
    get_or_404,
    pagination_params,
)
from app.models.admin import (
    AdminBookingData,
    AdminBookingListResponse,
    AdminDashboardStats,
    AdminEarningsResponse,
    AdminPatientData,
    AdminPatientListResponse,
    AdminPatientUpdate,
    AdminRecentActivity,
    AdminTherapistData,
    AdminTherapistListResponse,
    AdminTherapistUpdate,
)
from app.models.complaint import (
    ComplaintCreate,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintUpdate,
)
from app.services.admin import (
    get_admin_bookings,
    get_admin_dashboard_stats,
    get_admin_earnings,
    get_admin_patient,
    get_admin_patients,
    get_admin_recent_activity,
    get_admin_therapist,
    get_admin_therapists,
    update_admin_therapist,
    delete_admin_therapist,
    update_admin_patient,
    delete_admin_patient,
)
from app.services.complaint import (
    create_complaint,
    delete_complaint,
    get_complaint,
    get_complaints,
    update_complaint,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: str | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    where = {}
    if role:
        where["role"] = role.upper()
    users = await db.user.find_many(
        where=where, order={"createdAt": "desc"}, **pagination
    )
    return [UserResponse.model_validate(u) for u in users]


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    new_status: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "user", user_id)
    updated = await db.user.update(
        where={"id": user_id},
        data={"status": getattr(UserStatus, new_status.upper(), UserStatus.APPROVED)},
    )
    return UserResponse.model_validate(updated)


@router.get("/therapists", response_model=AdminTherapistListResponse)
async def list_therapists_admin(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    specialty: str | None = None,
    status: str | None = None,
    city: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "asc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_admin_therapists(
        db,
        skip=skip,
        limit=limit,
        search=search,
        specialty=specialty,
        status=status,
        city=city,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return AdminTherapistListResponse(items=items, total=total)


@router.get("/therapists/pending", response_model=list[UserResponse])
async def list_pending_therapists(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    users = await db.user.find_many(
        where={"role": "THERAPIST", "status": "PENDING"},
        order={"createdAt": "desc"},
    )
    return [UserResponse.model_validate(u) for u in users]


@router.get("/therapists/{therapist_id}", response_model=AdminTherapistData)
async def get_therapist_admin(
    therapist_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await get_admin_therapist(db, therapist_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.put("/therapists/{therapist_id}", response_model=AdminTherapistData)
async def update_therapist_admin(
    therapist_id: str,
    data: AdminTherapistUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await update_admin_therapist(
        db, therapist_id, data.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.delete("/therapists/{therapist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_therapist_admin(
    therapist_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    deleted = await delete_admin_therapist(db, therapist_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/patients", response_model=AdminPatientListResponse)
async def list_patients_admin(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    status: str | None = None,
    city: str | None = None,
    therapistId: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "asc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_admin_patients(
        db,
        skip=skip,
        limit=limit,
        search=search,
        date_from=dateFrom,
        date_to=dateTo,
        status=status,
        city=city,
        therapist_id=therapistId,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return AdminPatientListResponse(items=items, total=total)


@router.get("/patients/{patient_id}", response_model=AdminPatientData)
async def get_patient_admin(
    patient_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await get_admin_patient(db, patient_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.put("/patients/{patient_id}", response_model=AdminPatientData)
async def update_patient_admin(
    patient_id: str,
    data: AdminPatientUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await update_admin_patient(
        db, patient_id, data.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient_admin(
    patient_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    deleted = await delete_admin_patient(db, patient_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/dashboard/stats", response_model=AdminDashboardStats)
async def dashboard_stats(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return await get_admin_dashboard_stats(db)


@router.get("/dashboard/earnings", response_model=AdminEarningsResponse)
async def dashboard_earnings(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return await get_admin_earnings(db)


@router.get("/dashboard/recent-activity", response_model=list[AdminRecentActivity])
async def dashboard_recent_activity(
    limit: int = 10,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return await get_admin_recent_activity(db, limit)


@router.get("/bookings", response_model=AdminBookingListResponse)
async def list_bookings_admin(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "desc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_admin_bookings(
        db,
        skip=skip,
        limit=limit,
        search=search,
        status=status,
        date_from=dateFrom,
        date_to=dateTo,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return AdminBookingListResponse(items=items, total=total)


@router.get("/bookings/new-count")
async def new_booking_count(
    since: str | None = None,
    _=Depends(get_admin_user),
    db: Prisma =Depends(get_db),
):
    where: dict = {}
    if since:
        from datetime import datetime as dt
        try:
            parsed = dt.fromisoformat(since.replace("Z", "+00:00"))
            where["createdAt"] = {"gt": parsed}
        except (ValueError, TypeError):
            pass

    count = await db.session.count(where=where)
    return {"count": count}


# ── Complaints ──


@router.get("/complaints", response_model=ComplaintListResponse)
async def list_complaints(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    complainantId: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "desc",
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_complaints(
        db,
        skip=skip,
        limit=limit,
        search=search,
        type_filter=type,
        status=status,
        priority=priority,
        category=category,
        complainant_id=complainantId,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return ComplaintListResponse(
        items=[ComplaintResponse.model_validate(c) for c in items],
        total=total,
    )


@router.post("/complaints", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
async def submit_complaint(
    data: ComplaintCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    complaint = await create_complaint(db, data.model_dump())
    return ComplaintResponse.model_validate(complaint)


@router.put("/complaints/{complaint_id}", response_model=ComplaintResponse)
async def update_complaint_by_id(
    complaint_id: str,
    data: ComplaintUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "complaint", complaint_id)
    updated = await update_complaint(
        db, complaint_id, data.model_dump(exclude_none=True)
    )
    return ComplaintResponse.model_validate(updated)


@router.delete("/complaints/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_complaint_by_id(
    complaint_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "complaint", complaint_id)
    await delete_complaint(db, complaint_id)
