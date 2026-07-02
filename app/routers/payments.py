from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from prisma.enums import Role

from app.database import get_db
from app.deps import get_admin_user, get_current_user
from app.models.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
)
from app.services.payment import (
    create_payment,
    get_all_payments,
    get_payment,
    get_payments_for_user,
    update_payment,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def make_payment(
    data: PaymentCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    payment = await create_payment(
        db,
        {
            "userId": current_user.id,
            "amount": data.amount,
            "method": data.method,
            "sessionId": data.sessionId,
        },
    )
    return PaymentResponse.model_validate(payment)


@router.get("", response_model=PaymentListResponse)
async def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role == Role.ADMIN:
        payments, total = await get_all_payments(db, skip=skip, limit=limit)
    else:
        payments, total = await get_payments_for_user(
            db, current_user.id, skip=skip, limit=limit
        )
    return PaymentListResponse(
        payments=[PaymentResponse.model_validate(p) for p in payments],
        total=total,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_by_id(
    payment_id: str,
    db: Prisma = Depends(get_db),
):
    payment = await get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return PaymentResponse.model_validate(payment)


@router.put("/{payment_id}/status", response_model=PaymentResponse)
async def update_payment_status(
    payment_id: str,
    status: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    payment = await get_payment(db, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    updated = await update_payment(db, payment_id, {"status": status})
    return PaymentResponse.model_validate(updated)
