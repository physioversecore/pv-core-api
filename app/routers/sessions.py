from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    reverse_for_session,
    notify_referral_rewarded,
    notify_session_booked,
    notify_session_cancelled,
    notify_session_rescheduled,
    notify_session_status_change,
    award_referral_for_session,
    PaginationParams,
    RescheduleRequest,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
    create_session,
    delete_session,
    get_all_sessions,
    get_current_user,
    get_db,
    get_or_404,
    get_session,
    get_sessions_for_patient,
    get_sessions_for_therapist,
    get_therapist_by_user,
    pagination_params,
    reschedule_session,
    update_session,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "", response_model=SessionResponse, status_code=status.HTTP_201_CREATED
)
async def book_session(
    data: SessionCreate,
    background_tasks: BackgroundTasks,
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

    # Off the response path: the patient gets their booking back even if the
    # feed write fails.
    background_tasks.add_task(notify_session_booked, db, session["id"])
    return SessionResponse.model_validate(session)


@router.patch("/{session_id}/reschedule", response_model=SessionResponse)
async def reschedule_session_by_id(
    session_id: str,
    data: RescheduleRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Prisma =Depends(get_db),
):
    if current_user.role != Role.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    updated, error = await reschedule_session(
        db, session_id, current_user.id, data.newDate, data.newTime
    )
    if error == "CONFLICT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That slot was just booked — please choose another.",
        )
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error
        )
    background_tasks.add_task(notify_session_rescheduled, db, session_id)
    return SessionResponse.model_validate(updated)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role == Role.PATIENT:
        sessions, total = await get_sessions_for_patient(
            db, current_user.id, **pagination
        )
    elif current_user.role == Role.THERAPIST:
        therapist = await get_therapist_by_user(db, current_user.id)
        if not therapist:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        sessions, total = await get_sessions_for_therapist(
            db, therapist.id, **pagination
        )
    elif current_user.role == Role.ADMIN:
        sessions, total = await get_all_sessions(db, **pagination)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_by_id(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return SessionResponse.model_validate(session)


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session_by_id(
    session_id: str,
    data: SessionUpdate,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    session = await get_or_404(db, "session", session_id)
    if current_user.role == Role.ADMIN:
        pass
    elif current_user.role == Role.THERAPIST:
        therapist = await get_therapist_by_user(db, current_user.id)
        if not therapist or session.therapistId != therapist.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    elif session.patientId != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    previous_status = session.status
    updated = await update_session(
        db, session_id, data.model_dump(exclude_none=True)
    )

    # Upstream's admin-feed logging runs first and unchanged; the referral
    # ledger hangs off the same transition below.
    new_status = data.model_dump(exclude_none=True).get("status")
    if new_status:
        from app.services.notification import log_admin_notification
        from app.services.session import _enrich_session
        # A real Prisma row always *has* `patient` (None unless included), so
        # the old `hasattr` branch handed a model object to `.get()` and every
        # status change 500'd. `_enrich_session` flattens either shape, and the
        # names it produces are the same ones the branch was reaching for.
        enriched = _enrich_session(session)
        patient_name = enriched.get("patientName") or "Unknown"
        therapist_name = enriched.get("therapistName") or "Unknown"
        if new_status == "CANCELLED":
            await log_admin_notification(
                db,
                category="booking",
                message=f"Booking cancelled — {patient_name} with {therapist_name}",
                action_type="booking",
                action_id=session_id,
            )
        elif new_status == "RESCHEDULE_REQUESTED":
            await log_admin_notification(
                db,
                category="reschedule",
                message=f"Reschedule requested for {patient_name}'s session with {therapist_name}",
                action_type="booking",
                action_id=session_id,
            )

    # Referral points pay out on a *completed* session, not a booked one --
    # book-then-cancel would otherwise be free money. Only on the transition,
    # so re-saving a completed session cannot pay twice (the ledger's
    # idempotency key is the backstop).
    #
    # Read from the updated row rather than the request: upstream's new_status
    # above is request-only and is None when the caller changed something else,
    # which would silently skip the award.
    effective_status = getattr(updated, "status", None) or new_status

    # The per-user feed hangs off the *transition*, not the write: this
    # endpoint also edits notes and times, and a client that re-saves the same
    # status must not announce it twice.
    background_tasks.add_task(
        notify_session_status_change,
        db,
        session_id,
        new_status=effective_status,
        previous_status=previous_status,
        actor_user_id=current_user.id,
    )

    if effective_status == "COMPLETED" and previous_status != "COMPLETED":
        awarded = await award_referral_for_session(db, session)
        for user_id, row in awarded:
            background_tasks.add_task(
                notify_referral_rewarded,
                db,
                user_id,
                row.delta,
                transaction_id=getattr(row, "id", None),
            )
    elif effective_status == "CANCELLED" and previous_status == "COMPLETED":
        # A completed session that is later cancelled or refunded takes its
        # award with it.
        await reverse_for_session(db, session_id, "Session cancelled after completion")

    return SessionResponse.model_validate(updated)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    session = await get_or_404(db, "session", session_id)
    if (
        session.patientId != current_user.id
        and current_user.role != Role.ADMIN
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    # Awaited rather than backgrounded, unlike every other producer here: this
    # endpoint hard-deletes the row, and a background task would run after it
    # is gone with no names or times left to write. `safe_notify` swallows, so
    # an inline call still cannot fail the delete.
    await notify_session_cancelled(db, session_id, actor_user_id=current_user.id)
    await delete_session(db, session_id)
