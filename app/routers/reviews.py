from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from prisma.enums import Role

from app import (
    PaginationParams,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    TherapistToRate,
    create_review,
    get_completed_sessions_without_review,
    get_current_user,
    get_db,
    get_review_by_patient_and_therapist,
    get_review_by_session,
    get_reviews_for_patient,
    pagination_params,
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/therapists-to-rate", response_model=list[TherapistToRate])
async def list_therapists_to_rate(
    limit: int = Query(100, ge=0),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    sessions = await get_completed_sessions_without_review(db, current_user.id, limit=limit)
    return [
        TherapistToRate(
            sessionId=s.id,
            therapistId=s.therapist.id,
            therapistName=s.therapist.name,
            sessionDate=s.date,
            sessionType=s.type,
        )
        for s in sessions
    ]


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    data: ReviewCreate,
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    if current_user.role != Role.PATIENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if data.rating < 1 or data.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5",
        )

    existing = await get_review_by_session(db, data.sessionId)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session has already been reviewed",
        )

    session = await db.session.find_unique(
        where={"id": data.sessionId},
    )
    if not session or session.patientId != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    already = await get_review_by_patient_and_therapist(db, current_user.id, session.therapistId)
    if already:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this therapist",
        )

    review = await create_review(
        db,
        {
            "sessionId": data.sessionId,
            "patientId": current_user.id,
            "therapistId": session.therapistId,
            "rating": data.rating,
            "comment": data.comment,
        },
    )
    return ReviewResponse.model_validate(review)


@router.get("", response_model=ReviewListResponse)
async def list_my_reviews(
    pagination: PaginationParams = Depends(pagination_params),
    current_user=Depends(get_current_user),
    db: Prisma = Depends(get_db),
):
    reviews, total = await get_reviews_for_patient(
        db, current_user.id, **pagination
    )
    return ReviewListResponse(
        reviews=[ReviewResponse.model_validate(r) for r in reviews],
        total=total,
    )
