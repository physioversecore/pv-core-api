from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import UserStatus

from app import (
    PaginationParams,
    UserResponse,
    get_admin_user,
    get_db,
    get_or_404,
    pagination_params,
)
from app.models.admin import AdminDashboardStats, AdminEarningsResponse, AdminRecentActivity
from app.services.admin import (
    get_admin_dashboard_stats,
    get_admin_earnings,
    get_admin_recent_activity,
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
