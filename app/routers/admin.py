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
    AdminCreateTherapistRequest,
    AdminDashboardStats,
    AdminEarningsResponse,
    AdminPatientData,
    AdminPatientListResponse,
    AdminPatientUpdate,
    AdminPerformanceData,
    AdminPerformanceListResponse,
    AdminPerformanceUpdate,
    AdminRecentActivity,
    AdminTherapistCreatedResponse,
    AdminTherapistData,
    AdminTherapistListResponse,
    AdminTherapistUpdate,
    RemoveFromTeamRequest,
    ResolveRequest,
    ScheduleReviewRequest,
)
from app.models.complaint import (
    ComplaintCreate,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintUpdate,
)
from app.models.service_area import (
    ServiceAreaCreate,
    ServiceAreaListResponse,
    ServiceAreaResponse,
    ServiceAreaUpdate,
    TherapistAssignRequest,
)
from app.services.admin import (
    create_therapist_by_admin,
    delete_admin_performance,
    delete_admin_patient,
    delete_admin_therapist,
    get_admin_bookings,
    get_admin_dashboard_stats,
    get_admin_earnings,
    get_admin_patient,
    get_admin_patients,
    get_admin_performance,
    get_admin_performance_detail,
    get_admin_recent_activity,
    get_admin_therapist,
    get_admin_therapists,
    remove_from_team,
    resolve_therapist,
    schedule_review,
    update_admin_performance,
    update_admin_patient,
    update_admin_therapist,
)
from app.services.complaint import (
    create_complaint,
    delete_complaint,
    get_complaint,
    get_complaints,
    update_complaint,
)
from app.services.service_area import (
    assign_therapist_to_area,
    create_service_area,
    delete_service_area,
    get_service_area,
    get_service_areas,
    update_service_area,
)
from app.models.refund import (
    AssignRequest,
    ManualCaseCreate,
    ManualCaseResponse,
    RefundCreate,
    RefundListResponse,
    RefundResponse,
    RefundStatsResponse,
    RefundUpdate,
)
from app.services.refund import (
    assign_refund,
    create_manual_case,
    create_refund,
    delete_refund,
    get_refund,
    get_refund_stats,
    get_refunds,
    update_refund,
)
from app.services.activity_log import log_admin_activity, get_activity_logs
from app.models.verification import (
    VerificationCreate,
    VerificationListResponse,
    VerificationResponse,
    VerificationUpdate,
)
from app.services.verification import (
    create_verification,
    delete_verification,
    get_verification,
    get_verifications,
    update_verification,
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
        where=where, order={"createdAt": "desc"}, skip=pagination["skip"], take=pagination["limit"]
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


@router.post("/therapists", response_model=AdminTherapistCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_therapist_by_admin_endpoint(
    data: AdminCreateTherapistRequest,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing_user = await db.user.find_unique(where={"email": data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    result = await create_therapist_by_admin(db, data.model_dump())
    return AdminTherapistCreatedResponse(**result)


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


@router.get("/complaints/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint_by_id(
    complaint_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    complaint = await get_complaint(db, complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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
    await log_admin_activity(db, _.id, "UPDATE_COMPLAINT", "Complaint", complaint_id)
    return ComplaintResponse.model_validate(updated)


@router.put("/complaints/{complaint_id}/assign", response_model=ComplaintResponse)
async def assign_complaint_to_admin(
    complaint_id: str,
    body: AssignRequest,
    current_user=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "complaint", complaint_id)
    updated = await assign_complaint(db, complaint_id, body.assigneeId)
    await log_admin_activity(db, current_user.id, "ASSIGN_COMPLAINT", "Complaint", complaint_id, {"assigneeId": body.assigneeId})
    return ComplaintResponse.model_validate(updated)


@router.delete("/complaints/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_complaint_by_id(
    complaint_id: str,
    current_user=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "complaint", complaint_id)
    await delete_complaint(db, complaint_id)
    await log_admin_activity(db, current_user.id, "DELETE_COMPLAINT", "Complaint", complaint_id)


# ── Service Areas ──


@router.get("/service-areas", response_model=ServiceAreaListResponse)
async def list_service_areas(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "asc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_service_areas(
        db,
        skip=skip,
        limit=limit,
        search=search,
        status=status,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return ServiceAreaListResponse(items=items, total=total)


@router.get("/service-areas/{area_id}", response_model=ServiceAreaResponse)
async def get_service_area_by_id(
    area_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await get_service_area(db, area_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.post("/service-areas", response_model=ServiceAreaResponse, status_code=status.HTTP_201_CREATED)
async def create_service_area_endpoint(
    data: ServiceAreaCreate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return await create_service_area(db, data.model_dump())


@router.put("/service-areas/{area_id}", response_model=ServiceAreaResponse)
async def update_service_area_endpoint(
    area_id: str,
    data: ServiceAreaUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await update_service_area(db, area_id, data.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.delete("/service-areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_area_endpoint(
    area_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    deleted = await delete_service_area(db, area_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post("/service-areas/{area_id}/assign", response_model=ServiceAreaResponse)
async def assign_therapist_to_area_endpoint(
    area_id: str,
    data: TherapistAssignRequest,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await assign_therapist_to_area(db, area_id, data.therapistId)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


# ── Performance ──


@router.get("/performance", response_model=AdminPerformanceListResponse)
async def list_performance(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    minRating: float | None = None,
    sortBy: str | None = None,
    sortOrder: str = "asc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_admin_performance(
        db,
        skip=skip,
        limit=limit,
        search=search,
        status=status,
        min_rating=minRating,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return AdminPerformanceListResponse(items=items, total=total)


@router.get("/performance/{therapist_id}", response_model=AdminPerformanceData)
async def get_performance_detail(
    therapist_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await get_admin_performance_detail(db, therapist_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.put("/performance/{therapist_id}", response_model=AdminPerformanceData)
async def update_performance(
    therapist_id: str,
    data: AdminPerformanceUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await update_admin_performance(
        db, therapist_id, data.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.put("/performance/{therapist_id}/resolve", response_model=AdminPerformanceData)
async def resolve_performance(
    therapist_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await resolve_therapist(db, therapist_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.post("/performance/{therapist_id}/schedule-review")
async def schedule_therapist_review(
    therapist_id: str,
    data: ScheduleReviewRequest,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await schedule_review(db, therapist_id, data.model_dump())
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.put("/performance/{therapist_id}/remove")
async def remove_therapist_from_team(
    therapist_id: str,
    data: RemoveFromTeamRequest,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await remove_from_team(db, therapist_id, data.reason)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return result


@router.delete("/performance/{therapist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance(
    therapist_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    deleted = await delete_admin_performance(db, therapist_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


# ── Verifications ──


@router.get("/verifications", response_model=VerificationListResponse)
async def list_verifications(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    documentType: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    reportedBy: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "desc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_verifications(
        db,
        skip=skip,
        limit=limit,
        search=search,
        document_type=documentType,
        status=status,
        severity=severity,
        reported_by=reportedBy,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return VerificationListResponse(items=[VerificationResponse(**i) for i in items], total=total)


@router.post("/verifications", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
async def create_verification_endpoint(
    data: VerificationCreate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    therapist = await db.therapist.find_unique(where={"id": data.therapistId})
    if not therapist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Therapist not found")
    payload = data.model_dump()
    result = await create_verification(db, payload)
    return VerificationResponse(**result)


@router.put("/verifications/{verification_id}", response_model=VerificationResponse)
async def update_verification_endpoint(
    verification_id: str,
    data: VerificationUpdate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await get_verification(db, verification_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    payload = data.model_dump(exclude_none=True)
    if "expires" in payload and payload["expires"] == "":
        payload["expires"] = None
    result = await update_verification(db, verification_id, payload)
    return VerificationResponse(**result)


@router.put("/verifications/{verification_id}/suspend")
async def suspend_therapist_bookings(
    verification_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await get_verification(db, verification_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    result = await update_verification(db, verification_id, {"status": "Expired"})
    return VerificationResponse(**result)


@router.delete("/verifications/{verification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_verification_endpoint(
    verification_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    existing = await get_verification(db, verification_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await delete_verification(db, verification_id)


# ── Refunds ──


@router.get("/refunds", response_model=RefundListResponse)
async def list_refunds(
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    reason: str | None = None,
    status: str | None = None,
    dateFrom: str | None = None,
    dateTo: str | None = None,
    sortBy: str | None = None,
    sortOrder: str = "desc",
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_refunds(
        db,
        skip=skip,
        limit=limit,
        search=search,
        reason=reason,
        status=status,
        date_from=dateFrom,
        date_to=dateTo,
        sort_by=sortBy,
        sort_order=sortOrder,
    )
    return RefundListResponse(items=[RefundResponse(**i) for i in items], total=total)


@router.get("/refunds/stats", response_model=RefundStatsResponse)
async def refund_stats(
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return await get_refund_stats(db)


@router.get("/refunds/{refund_id}", response_model=RefundResponse)
async def get_refund_by_id(
    refund_id: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await get_refund(db, refund_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return RefundResponse(**result)


@router.post("/refunds", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
async def create_refund_endpoint(
    data: RefundCreate,
    current_user=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    patient = await db.user.find_unique(where={"id": data.patientId})
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    result = await create_refund(db, data.model_dump())
    await log_admin_activity(db, current_user.id, "CREATE_REFUND", "Refund", result["id"], {"amount": data.amount})
    return RefundResponse(**result)


@router.post("/refunds/manual-case", response_model=ManualCaseResponse)
async def create_manual_refund_case(
    payload: ManualCaseCreate,
    current_user=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return await create_manual_case(db, payload.model_dump(), current_user.id)


@router.put("/refunds/{refund_id}", response_model=RefundResponse)
async def update_refund_by_id(
    refund_id: str,
    data: RefundUpdate,
    current_user=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "refund", refund_id)
    updated = await update_refund(db, refund_id, data.model_dump(exclude_none=True))
    action = "UPDATE_REFUND"
    if data.status:
        if data.status == "Approved":
            action = "APPROVE_REFUND"
        elif data.status == "Denied":
            action = "DENY_REFUND"
    await log_admin_activity(db, current_user.id, action, "Refund", refund_id, {"status": data.status})
    return RefundResponse(**updated)


@router.put("/refunds/{refund_id}/assign", response_model=RefundResponse)
async def assign_refund_to_admin(
    refund_id: str,
    body: AssignRequest,
    current_user=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "refund", refund_id)
    updated = await assign_refund(db, refund_id, body.assigneeId)
    await log_admin_activity(db, current_user.id, "ASSIGN_REFUND", "Refund", refund_id, {"assigneeId": body.assigneeId})
    return RefundResponse(**updated)


@router.delete("/refunds/{refund_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_refund_by_id(
    refund_id: str,
    current_user=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "refund", refund_id)
    await delete_refund(db, refund_id)
    await log_admin_activity(db, current_user.id, "DELETE_REFUND", "Refund", refund_id)


# ── Activity Log ──


@router.get("/activity-log")
async def list_activity_log(
    skip: int = 0,
    limit: int = 50,
    adminId: str | None = None,
    targetType: str | None = None,
    actionType: str | None = None,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    items, total = await get_activity_logs(
        db, skip=skip, limit=limit,
        admin_id=adminId, target_type=targetType, action_type=actionType,
    )
    return {
        "items": [
            {
                "id": i.id,
                "timestamp": i.createdAt.isoformat(),
                "actor": i.adminId,
                "actorId": i.adminId,
                "actionType": i.action,
                "description": f"{i.action} on {i.targetType} {i.targetId}",
            }
            for i in items
        ],
        "total": total,
    }
