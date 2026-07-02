from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from prisma.enums import Role

from app.database import get_db
from app.deps import get_current_user
from app.models.report import ReportCreate, ReportResponse, ReportUpdate
from app.services.report import (
    create_report,
    delete_report,
    get_report,
    get_reports_for_patient,
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
    patient_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    pid = patient_id or current_user.id
    if current_user.role == Role.PATIENT:
        pid = current_user.id
    reports, _ = await get_reports_for_patient(db, pid, skip=skip, limit=limit)
    return [ReportResponse.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_by_id(
    report_id: str,
    db: Prisma = Depends(get_db),
):
    report = await get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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
    report = await get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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
    report = await get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await delete_report(db, report_id)
