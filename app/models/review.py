from datetime import datetime
from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    sessionId: str = Field(min_length=1, max_length=64)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


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
