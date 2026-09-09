from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    BookingPaymentRequest,
    BookingPaymentResponse,
    GatewayConfigError,
    GatewayError,
    GatewayInitiationResponse,
    PaginationParams,
    PaymentConfirmRequest,
    PaymentConfirmResponse,
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
    get_gateway,
    get_or_404,
    get_payment,
    get_payments_for_user,
    get_therapist_by_user,
    is_gateway_method,
    normalize_method,
    pagination_params,
    update_payment,
)
from app.services.payments import COMPLETED as PAYMENT_COMPLETED
from app.services.payments import CANCELLED as PAYMENT_CANCELLED
from app.services.payments import FAILED as PAYMENT_FAILED
from app.services.payments import PENDING as PAYMENT_PENDING

router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Booking flow ─────────────────────────────────────────────────────────────


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

    method = normalize_method(data.paymentMethod)
    is_gateway = is_gateway_method(method)

    payment = await create_payment(
        db,
        {
            "userId": current_user.id,
            "amount": data.fee + data.platformFee,
            "method": method.upper(),
            "sessionId": session["id"],
            "currency": data.currency,
            "platformFee": data.platformFee,
            "paymentType": data.paymentType,
            "transactionRef": data.transactionRef,
            "cardLast4": data.cardLast4,
            "walletMobile": data.walletMobile,
            "billingCountry": data.billingCountry,
            # Gateway payments start as PENDING; manual methods are immediately final.
            "status": PAYMENT_PENDING if is_gateway else PAYMENT_COMPLETED,
        },
    )

    from app.services.notification import log_admin_notification

    if not is_gateway:
        # Only log the notification for immediately confirmed (manual) payments.
        # Gateway payments will get notified via the confirm endpoint.
        await log_admin_notification(
            db,
            category="payment",
            message=(
                f"Payment of Rs {data.fee + data.platformFee:,.0f} "
                f"processed via {data.paymentMethod}"
            ),
            action_type="payment",
            action_id=payment.id,
        )

    initiation = None
    if is_gateway:
        gateway = get_gateway(method)
        try:
            initiate_payload = await gateway.initiate(
                db,
                payment,
                {
                    "customer": {
                        "name": current_user.name,
                        "email": current_user.email,
                        "phone": current_user.phone,
                    }
                },
            )
            initiation = GatewayInitiationResponse(
                type=initiate_payload.type,
                url=initiate_payload.url,
                formFields=initiate_payload.form_fields,
                expiresAt=initiate_payload.expires_at,
            )
            # The gateway may have updated payment (e.g. Khalti storing pidx in
            # transactionRef). Re-read so the response is consistent.
            payment = await get_payment(db, payment.id)
        except GatewayConfigError as exc:
            # Gateway not configured — let the patient know clearly instead of
            # silently marking the booking as paid.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )
        except GatewayError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Payment gateway error: {exc}",
            )

    return BookingPaymentResponse(
        session=SessionPaymentResponse.model_validate(session),
        payment=PaymentResponse.model_validate(payment),
        initiation=initiation,
    )


# ── Confirm (webhook / status refresh) ───────────────────────────────────────


@router.post(
    "/{payment_id}/confirm",
    response_model=PaymentConfirmResponse,
)
async def confirm_payment(
    payment_id: str,
    data: PaymentConfirmRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    payment = await get_or_404(db, "payment", payment_id)

    if current_user.role != Role.ADMIN and payment.userId != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    # Already settled — confirm is idempotent.
    if payment.status == PAYMENT_COMPLETED:
        return PaymentConfirmResponse(
            payment=PaymentResponse.model_validate(payment),
            result="already_completed",
        )

    gateway = get_gateway(payment.method)
    try:
        verification = await gateway.verify(db, payment, data.params)
    except (GatewayConfigError, GatewayError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment gateway error: {exc}",
        )

    new_status = verification.status
    updates: dict = {}
    if verification.ref:
        updates["transactionRef"] = verification.ref
    if payment.status != new_status:
        updates["status"] = new_status

    if updates:
        payment = await update_payment(db, payment.id, updates)

    # Log admin notification only on the first transition to COMPLETED.
    if new_status == PAYMENT_COMPLETED and payment.status != PAYMENT_COMPLETED:
        from app.services.notification import log_admin_notification

        await log_admin_notification(
            db,
            category="payment",
            message=(
                f"Payment {payment.id} completed via {payment.method} "
                f"(Rs {payment.amount:,.0f})"
            ),
            action_type="payment",
            action_id=payment.id,
        )

    return PaymentConfirmResponse(
        payment=PaymentResponse.model_validate(payment),
        result=new_status,
    )


@router.get("/{payment_id}/status", response_model=PaymentResponse)
async def get_payment_status(
    payment_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Return the current stored status of a payment. Client-side polling
    hits this after redirecting back from the gateway; the actual server-side
    verification happens via POST /confirm.
    """
    payment = await get_or_404(db, "payment", payment_id)
    if current_user.role != Role.ADMIN and payment.userId != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return PaymentResponse.model_validate(payment)


# ── Generic (non-booking) payment ────────────────────────────────────────────


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


# ── Listing / read ───────────────────────────────────────────────────────────


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


# ── Admin ────────────────────────────────────────────────────────────────────


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