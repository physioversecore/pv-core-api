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


class TodaySessionData(BaseModel):
    id: str
    time: str
    patient: str
    patientId: str
    address: str
    type: str
    status: str


class RecentUploadData(BaseModel):
    id: str
    patient: str
    kind: str
    title: str
    file: str
    date: str


class PublicProfileData(BaseModel):
    name: str
    specialty: str
    experience: int
    rating: float
    totalReviews: int


class RecentRatingData(BaseModel):
    id: str
    name: str
    stars: int
    text: str


class TherapistDashboardResponse(BaseModel):
    name: str
    sessionsThisWeek: int
    totalPatients: int
    earningsThisMonth: float
    averageRating: float
    todaySessions: list[TodaySessionData]
    recentUploads: list[RecentUploadData]
    publicProfile: PublicProfileData
    recentRatings: list[RecentRatingData]
    referralCode: str
    referralLink: str
