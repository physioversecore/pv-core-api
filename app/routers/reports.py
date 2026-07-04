from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    PaginationParams,
    ReportCreate,
    ReportResponse,
    ReportUpdate,
    create_report,
    delete_report,
    get_current_user,
    get_db,
    get_or_404,
    get_reports_for_patient,
    pagination_params,
    update_report,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post(
    "", response_model=ReportResponse, status_code=status.HTTP_201_CREATED
)
async def create_new_report(
    data: ReportCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    report = await create_report(db, data.model_dump())
    return ReportResponse.model_validate(report)


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    patient_id: str | None = None,
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role == Role.PATIENT:
        pid = current_user.id
    else:
        pid = patient_id
        if not pid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required for therapists and admins",
            )
    reports, _ = await get_reports_for_patient(db, pid, **pagination)
    return [ReportResponse.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_by_id(
    report_id: str,
    db: Prisma = Depends(get_db),
):
    report = await get_or_404(db, "report", report_id)
    return ReportResponse.model_validate(report)


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report_by_id(
    report_id: str,
    data: ReportUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await get_or_404(db, "report", report_id)
    updated = await update_report(
        db, report_id, data.model_dump(exclude_none=True)
    )
    return ReportResponse.model_validate(updated)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_by_id(
    report_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role not in (Role.THERAPIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await get_or_404(db, "report", report_id)
    await delete_report(db, report_id)
