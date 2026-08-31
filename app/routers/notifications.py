from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app import (
    NotificationCreate,
    NotificationListResponse,
    NotificationResponse,
    PaginationParams,
    create_notification,
    get_admin_user,
    get_current_user,
    get_db,
    list_notifications,
    mark_all_read,
    mark_read,
    pagination_params,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
async def my_notifications(
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    items, total, unread = await list_notifications(
        db, current_user.id, **pagination
    )
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread=unread,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def read_one(
    notification_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    # Scoped by user inside the service, so a valid id belonging to someone
    # else is a 404 rather than a silent cross-account write.
    updated = await mark_read(db, current_user.id, notification_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return NotificationResponse.model_validate(updated)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    await mark_all_read(db, current_user.id)


@router.post(
    "", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED
)
async def create_for_user(
    data: NotificationCreate,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    """Admin-only. In-app events are raised by services, not over HTTP."""
    created = await create_notification(
        db,
        data.userId,
        type=data.type,
        title=data.title,
        body=data.body,
        ref_type=data.refType,
        ref_id=data.refId,
    )
    return NotificationResponse.model_validate(created)
