from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from prisma.enums import UserStatus

from app.database import get_db
from app.deps import get_admin_user
from app.models.auth import UserResponse
from app.models.therapist import TherapistResponse
from app.models.payment import PaymentListResponse, PaymentResponse
from app.models.session import SessionListResponse, SessionResponse
from app.services.payment import get_all_payments
from app.services.session import get_all_sessions, update_session

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    where = {}
    if role:
        where["role"] = role.upper()
    users = await db.user.find_many(
        where=where, skip=skip, take=limit, order={"createdAt": "desc"}
    )
    return [UserResponse.model_validate(u) for u in users]


@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    status: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    user = await db.user.find_unique(where={"id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    updated = await db.user.update(
        where={"id": user_id}, data={"status": getattr(UserStatus, status.upper(), UserStatus.APPROVED)}
    )
    return UserResponse.model_validate(updated)


@router.get("/payments", response_model=PaymentListResponse)
async def list_all_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    payments, total = await get_all_payments(db, skip=skip, limit=limit)
    return PaymentListResponse(
        payments=[PaymentResponse.model_validate(p) for p in payments],
        total=total,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_all_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    sessions, total = await get_all_sessions(db, skip=skip, limit=limit)
    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


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
