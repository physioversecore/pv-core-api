from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    PaginationParams,
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    create_payment,
    get_admin_user,
    get_all_payments,
    get_current_user,
    get_db,
    get_or_404,
    get_payments_for_user,
    pagination_params,
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
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role == Role.ADMIN:
        payments, total = await get_all_payments(db, **pagination)
    else:
        payments, total = await get_payments_for_user(
            db, current_user.id, **pagination
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
    payment = await get_or_404(db, "payment", payment_id)
    return PaymentResponse.model_validate(payment)


@router.put("/{payment_id}/status", response_model=PaymentResponse)
async def update_payment_status(
    payment_id: str,
    new_status: str,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    await get_or_404(db, "payment", payment_id)
    updated = await update_payment(db, payment_id, {"status": new_status})
    return PaymentResponse.model_validate(updated)
