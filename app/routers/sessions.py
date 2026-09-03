from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
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
    return SessionResponse.model_validate(session)


@router.patch("/{session_id}/reschedule", response_model=SessionResponse)
async def reschedule_session_by_id(
    session_id: str,
    data: RescheduleRequest,
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
    updated = await update_session(
        db, session_id, data.model_dump(exclude_none=True)
    )

    new_status = data.model_dump(exclude_none=True).get("status")
    if new_status:
        from app.services.notification import log_admin_notification
        from app.services.session import _enrich_session
        enriched = _enrich_session(session) if not hasattr(session, "patient") else session
        patient_name = enriched.get("patient", {}).get("name", "Unknown") if isinstance(enriched.get("patient"), dict) else getattr(getattr(session, "patient", None), "name", "Unknown")
        therapist_name = enriched.get("therapist", {}).get("name", "Unknown") if isinstance(enriched.get("therapist"), dict) else getattr(getattr(session, "therapist", None), "name", "Unknown")
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
    await delete_session(db, session_id)
