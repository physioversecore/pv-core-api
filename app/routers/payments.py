from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    BookingPaymentRequest,
    BookingPaymentResponse,
    PaginationParams,
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    SessionPaymentResponse,
    create_payment,
    create_session,
    get_admin_user,
    get_all_payments,
    get_current_user,
    get_db,
    get_or_404,
    get_payments_for_user,
    get_therapist_by_user,
    pagination_params,
    update_payment,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/process",
    response_model=BookingPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def process_booking_payment(
    data: BookingPaymentRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    try:
        session = await create_session(
            db,
            {
                "therapistId": data.therapistId,
                "patientId": current_user.id,
                "date": data.date,
                "time": data.time,
                "type": data.type.upper(),
                "address": data.address,
                "fee": data.fee,
                "familyMemberId": data.familyMemberId,
                "notes": data.notes,
            },
        )
    except ValueError as e:
        if str(e) == "CONFLICT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That time slot was just booked — please choose another.",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    payment = await create_payment(
        db,
        {
            "userId": current_user.id,
            "amount": data.fee + data.platformFee,
            "method": data.paymentMethod.upper(),
            "sessionId": session["id"],
            "currency": data.currency,
            "platformFee": data.platformFee,
            "paymentType": data.paymentType,
            "transactionRef": data.transactionRef,
            "cardLast4": data.cardLast4,
            "walletMobile": data.walletMobile,
            "billingCountry": data.billingCountry,
            "status": "COMPLETED",
        },
    )

    from app.services.notification import log_admin_notification
    await log_admin_notification(
        db,
        category="payment",
        message=f"Payment of Rs {data.fee + data.platformFee:,.0f} processed via {data.paymentMethod}",
        action_type="payment",
        action_id=payment.id,
    )

    return BookingPaymentResponse(
        session=SessionPaymentResponse.model_validate(session),
        payment=PaymentResponse.model_validate(payment),
    )


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
            "currency": data.currency,
            "platformFee": data.platformFee,
            "paymentType": data.paymentType,
            "transactionRef": data.transactionRef,
            "cardLast4": data.cardLast4,
            "walletMobile": data.walletMobile,
            "billingCountry": data.billingCountry,
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
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    payment = await get_or_404(db, "payment", payment_id)
    if current_user.role != Role.ADMIN and payment.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
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
