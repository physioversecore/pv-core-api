from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    RateChangeListResponse,
    RateChangeRequestCreate,
    RateChangeRequestResponse,
    approve_rate_change,
    create_rate_change,
    get_current_user,
    get_db,
    get_rate_changes_for_admin,
    get_therapist_by_user,
    get_therapist_rate_changes,
    reject_rate_change,
)
from app.deps import get_admin_user

router = APIRouter(prefix="/rate-change", tags=["Rate change"])


async def _resolve_therapist(current_user, db: Prisma):
    if current_user.role != Role.THERAPIST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    therapist = await get_therapist_by_user(db, current_user.id)
    if not therapist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return therapist


@router.post("")
async def request_rate_change(
    data: RateChangeRequestCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    therapist = await _resolve_therapist(current_user, db)
    return await create_rate_change(db, therapist.id, data.model_dump())


@router.get("")
async def list_rate_changes(
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role == Role.ADMIN:
        items, total = await get_rate_changes_for_admin(
            db, skip=skip, limit=limit, status=status
        )
        return RateChangeListResponse(items=items, total=total)
    therapist = await _resolve_therapist(current_user, db)
    items = await get_therapist_rate_changes(db, therapist.id)
    return RateChangeListResponse(items=items, total=len(items))


@router.put("/{request_id}/approve")
async def approve_request(
    request_id: str,
    data: dict = {},
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await approve_rate_change(db, request_id, data.get("adminNotes", ""))
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["error"])
    return result


@router.put("/{request_id}/reject")
async def reject_request(
    request_id: str,
    data: dict = {},
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    result = await reject_rate_change(db, request_id, data.get("adminNotes", ""))
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["error"])
    return result