from datetime import datetime
from pydantic import BaseModel


class ReviewCreate(BaseModel):
    sessionId: str
    rating: int
    comment: str | None = None


class TherapistToRate(BaseModel):
    sessionId: str
    therapistId: str
    therapistName: str
    sessionDate: datetime
    sessionType: str


class ReviewResponse(BaseModel):
    id: str
    sessionId: str
    patientId: str
    therapistId: str
    rating: int
    comment: str | None = None
    createdAt: datetime

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    reviews: list[ReviewResponse]
    total: int
