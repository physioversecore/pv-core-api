from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    PaginationParams,
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
            "notes": data.notes,
        },
    )
    return SessionResponse.model_validate(session)


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
    if (
        session.patientId != current_user.id
        and current_user.role != Role.ADMIN
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    updated = await update_session(
        db, session_id, data.model_dump(exclude_none=True)
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
