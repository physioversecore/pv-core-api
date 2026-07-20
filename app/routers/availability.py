from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    ApplyScheduleRequest,
    AuditLogCreateRequest,
    AuditLogEntryResponse,
    BlockDateRequest,
    BlockDateResponse,
    BlockInfoResponse,
    BlockRangeRequest,
    BlockRangeResponse,
    BulkSlotUpdate,
    GenerateAvailabilityRequest,
    get_therapist,
    MonthlyGridResponse,
    OpenFullMonthRequest,
    OpenMonthResponse,
    PaginatedAuditLogResponse,
    RecurringApplyResponse,
    RecurringPatternCreate,
    RecurringPatternListResponse,
    SlotInfo,
    SlotRangeResponse,
    SlotUpdate,
    SlotUpdateResponse,
    UnblockRequest,
    WorkingHoursResponse,
    WorkingHoursUpdate,
    apply_recurring_pattern,
    apply_schedule,
    block_date,
    block_range,
    bulk_update_slots,
    create_audit_entry,
    create_block_request,
    delete_audit_entry,
    delete_recurring_pattern,
    generate_availability,
    get_audit_entries,
    get_current_user,
    get_db,
    get_monthly_availability,
    get_pending_block_requests,
    get_recurring_patterns,
    get_slots_for_range,
    get_therapist_block_requests,
    get_therapist_by_user,
    get_working_days,
    get_working_hours,
    open_full_month,
    approve_block_request,
    reject_block_request,
    set_slot_status,
    toggle_recurring_pattern,
    unblock_item,
    update_working_hours,
)

router = APIRouter(prefix="/availability", tags=["Availability"])


async def _resolve_therapist(current_user, db: Prisma):
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    therapist = await get_therapist_by_user(db, current_user.id)
    if not therapist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return therapist


@router.get("/working-hours", response_model=WorkingHoursResponse)
async def read_working_hours(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    await _resolve_therapist(current_user, db)
    return await get_working_hours(db, current_user.id)


@router.put("/working-hours", response_model=WorkingHoursResponse)
async def edit_working_hours(
    data: WorkingHoursUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    await _resolve_therapist(current_user, db)
    return await update_working_hours(db, current_user.id, data.model_dump())


@router.post("/apply-schedule")
async def apply_schedule_endpoint(
    data: ApplyScheduleRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    await _resolve_therapist(current_user, db)
    return await apply_schedule(db, current_user.id, data.model_dump())


@router.get("", response_model=MonthlyGridResponse)
async def list_availability(
    month: int,
    year: int,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await get_monthly_availability(db, therapist.id, month, year)


@router.post("/slot", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_slot(
    data: SlotUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    await set_slot_status(db, therapist.id, data.model_dump())


@router.post("/bulk", response_model=SlotUpdateResponse)
async def bulk_toggle_slots(
    data: BulkSlotUpdate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    count = await bulk_update_slots(
        db, therapist.id, [s.model_dump() for s in data.slots]
    )
    return SlotUpdateResponse(updated=count)


@router.post("/recurring", response_model=RecurringApplyResponse)
async def save_recurring(
    data: RecurringPatternCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await apply_recurring_pattern(db, therapist.id, data.model_dump())


@router.get("/recurring", response_model=RecurringPatternListResponse)
async def list_recurring(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    patterns = await get_recurring_patterns(db, therapist.id)
    return RecurringPatternListResponse(patterns=patterns)


@router.delete("/recurring/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_recurring(
    pattern_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    await delete_recurring_pattern(db, therapist.id, pattern_id)


@router.put("/recurring/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def edit_recurring(
    pattern_id: str,
    data: dict,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    await toggle_recurring_pattern(
        db, therapist.id, pattern_id, data.get("isActive", True)
    )


@router.post("/open-month", response_model=OpenMonthResponse)
async def bulk_open_month(
    data: OpenFullMonthRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await open_full_month(db, therapist.id, data.model_dump())


@router.post("/block-date", response_model=BlockDateResponse)
async def bulk_block_date(
    data: BlockDateRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await block_date(db, therapist.id, data.model_dump())


@router.post("/generate", response_model=SlotUpdateResponse)
async def generate_slots(
    data: GenerateAvailabilityRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await generate_availability(db, therapist.id, data.model_dump())


@router.post("/block-range", response_model=BlockRangeResponse)
async def block_time_range(
    data: BlockRangeRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await block_range(db, therapist.id, data.model_dump())


@router.post("/unblock", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_time(
    data: UnblockRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    await unblock_item(db, therapist.id, data.date, data.time)


@router.get("/slots", response_model=SlotRangeResponse)
async def get_slots_range(
    from_date: str,
    to_date: str,
    therapist_id: str | None = None,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if therapist_id:
        target = await get_therapist(db, therapist_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Therapist not found")
    else:
        target = await _resolve_therapist(current_user, db)
    return await get_slots_for_range(db, target.id, from_date, to_date)


@router.get("/working-days")
async def get_working_days_endpoint(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await get_working_days(db, therapist.id)


@router.get("/audit-log", response_model=PaginatedAuditLogResponse)
async def list_audit(
    limit: int = 5,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await get_audit_entries(db, therapist.id, limit, offset)


@router.post("/audit-log", response_model=AuditLogEntryResponse)
async def add_audit(
    data: AuditLogCreateRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await create_audit_entry(db, therapist.id, data.model_dump())


@router.delete("/audit-log/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_audit(
    entry_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    await delete_audit_entry(db, therapist.id, entry_id)


@router.post("/block-request")
async def request_block(
    data: BlockRangeRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await create_block_request(db, therapist.id, data.model_dump())


@router.get("/block-requests")
async def list_block_requests(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role == Role.ADMIN:
        return await get_pending_block_requests(db)
    therapist = await _resolve_therapist(current_user, db)
    return await get_therapist_block_requests(db, therapist.id)


@router.put("/block-requests/{request_id}/approve")
async def approve_request(
    request_id: str,
    data: dict = {},
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return await approve_block_request(db, request_id, data.get("adminNotes", ""))


@router.put("/block-requests/{request_id}/reject")
async def reject_request(
    request_id: str,
    data: dict = {},
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return await reject_block_request(db, request_id, data.get("adminNotes", ""))
