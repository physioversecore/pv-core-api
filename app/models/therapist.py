from datetime import datetime
from pydantic import BaseModel


class TherapistCreate(BaseModel):
    name: str
    specialty: str
    city: str
    gender: str
    price: float
    experience: int
    bio: str


class TherapistUpdate(BaseModel):
    name: str | None = None
    specialty: str | None = None
    city: str | None = None
    gender: str | None = None
    price: float | None = None
    experience: int | None = None
    bio: str | None = None


class TherapistResponse(BaseModel):
    id: str
    userId: str
    name: str
    specialty: str
    city: str
    gender: str
    rating: float
    reviews: int
    price: float
    experience: int
    bio: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class TherapistListResponse(BaseModel):
    therapists: list[TherapistResponse]
    total: int
