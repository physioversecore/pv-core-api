from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app import (
    ApplyPointsRequest,
    ApplyPointsResponse,
    PaginationParams,
    PointBalanceResponse,
    PointGrantRequest,
    PointGrantResponse,
    PointTransactionListResponse,
    PointTransactionResponse,
    PointsConfig,
    ReferralEntry,
    ReferralSummaryResponse,
    get_admin_user,
    get_balance,
    get_config,
    get_current_user,
    get_db,
    get_or_404,
    grant,
    list_transactions,
    mature_pending,
    pagination_params,
    redeem,
    save_config,
)

router = APIRouter(prefix="/points", tags=["Points"])


@router.get("/me", response_model=PointBalanceResponse)
async def my_points(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    # Held awards mature on read: a balance is only observed when someone
    # looks, so there is nothing for a scheduler to do.
    await mature_pending(db, current_user.id)
    totals = await get_balance(db, current_user.id)
    config = await get_config(db)
    return PointBalanceResponse(**totals, pointToNpr=float(config["pointToNpr"]))


@router.get("/me/transactions", response_model=PointTransactionListResponse)
async def my_transactions(
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    items, total = await list_transactions(db, current_user.id, **pagination)
    return PointTransactionListResponse(
        transactions=[PointTransactionResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get("/me/referrals", response_model=ReferralSummaryResponse)
async def my_referrals(
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Code, link and the history list, for both roles.

    Replaces the split between GET /patients/me/referral and the therapist
    dashboard's referral fields, which also disagreed on link format.
    """
    config = await get_config(db)
    code = current_user.referralCode or ""

    referred = await db.user.find_many(
        where={"referredById": current_user.id}, order={"createdAt": "desc"}
    )

    entries = []
    for user in referred:
        rows = await db.pointtransaction.find_many(
            where={
                "userId": current_user.id,
                "type": "REFERRAL_EARN",
                "idempotencyKey": "referral:{}:referrer".format(user.id),
            }
        )
        row = rows[0] if rows else None
        if row is None:
            state, points = "JOINED", None
        elif row.status == "PENDING":
            state, points = "PENDING", row.delta
        elif row.status == "REVERSED":
            state, points = "REVERSED", None
        else:
            state, points = "REWARDED", row.delta

        entries.append(
            ReferralEntry(
                id=user.id,
                name=user.name,
                state=state,
                points=points,
                joinedAt=user.createdAt,
            )
        )

    # A therapist's headline is the therapist-to-therapist tier, which is the
    # figure their screen advertises; a patient sees the friend rate.
    if current_user.role == "THERAPIST":
        headline = int(config["referralAwardTherapistRefersTherapist"])
    else:
        headline = int(config["referralAwardPatientReferrer"])

    earned_rows = await db.pointtransaction.find_many(
        where={"userId": current_user.id, "type": "REFERRAL_EARN"}
    )
    total_earned = sum(r.delta for r in earned_rows if r.delta > 0)

    return ReferralSummaryResponse(
        code=code,
        link="https://sahayatri.np/r/{}".format(code),
        awardPoints=headline,
        totalEarned=total_earned,
        referrals=entries,
    )


@router.post("/sessions/{session_id}/apply", response_model=ApplyPointsResponse)
async def apply_to_session(
    session_id: str,
    data: ApplyPointsRequest,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    """Spend points against one of the caller's own bookings."""
    session = await get_or_404(db, "session", session_id)
    if session.patientId != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    row, error = await redeem(
        db, current_user.id, data.points, session_id=session_id, fee=session.fee
    )
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    config = await get_config(db)
    discount = data.points * float(config["pointToNpr"])
    return ApplyPointsResponse(
        pointsApplied=data.points,
        discountAmount=discount,
        # Gross fee, unchanged: the therapist is paid in full and the platform
        # funds the discount.
        sessionFee=session.fee,
        payable=max(session.fee - discount, 0.0),
    )


# -- Admin ------------------------------------------------------------------


@router.post("/admin/grant", response_model=PointGrantResponse)
async def admin_grant(
    data: PointGrantRequest,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    """Manual or bulk grant -- how a festival bonus is run.

    Deliberately not a campaign engine: a segment builder with scheduling is
    weeks of work for something run a few times a year.
    """
    granted = skipped = 0
    for user_id in data.userIds:
        row = await grant(
            db,
            user_id,
            delta=data.amount,
            type="PROMO_GRANT",
            status="AVAILABLE",
            reason=data.reason,
            ref_type="ADMIN",
            expires_at=data.expiresAt,
        )
        if row:
            granted += 1
        else:
            skipped += 1
    return PointGrantResponse(granted=granted, skipped=skipped)


@router.get("/admin/config")
async def read_config(_=Depends(get_admin_user), db: Prisma = Depends(get_db)):
    return await get_config(db)


@router.put("/admin/config")
async def write_config(
    data: PointsConfig,
    _=Depends(get_admin_user),
    db: Prisma = Depends(get_db),
):
    return await save_config(db, data.model_dump(exclude_unset=True))
