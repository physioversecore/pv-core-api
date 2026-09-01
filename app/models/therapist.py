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


class TherapistDocument(BaseModel):
    id: str
    documentType: str | None = None
    documentUrl: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    status: str | None = None
    note: str | None = None


class TherapistProfileResponse(BaseModel):
    id: str
    userId: str
    name: str
    email: str
    phone: str
    city: str
    specialty: str
    gender: str
    licenseNumber: str | None = None
    price: float
    experience: int
    bio: str
    mediaUrls: str | None = None
    photo: str | None = None
    documents: list[TherapistDocument] | None = None

    class Config:
        from_attributes = True


class TherapistProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    city: str | None = None
    specialty: str | None = None
    gender: str | None = None
    licenseNumber: str | None = None
    price: float | None = None
    experience: int | None = None
    bio: str | None = None
    mediaUrls: str | None = None


class ClinicBrief(BaseModel):
    """Workplace details for an information-only therapist.

    Resolved through the linked clinic rather than duplicated onto the
    therapist, so hours, services and address have one source of truth.
    """

    id: str
    name: str
    area: str = ""
    city: str = ""
    address: str = ""
    phone: str = ""
    hours: str = ""
    services: list[str] = []
    latitude: float | None = None
    longitude: float | None = None

    class Config:
        from_attributes = True


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

    # BOOKABLE therapists expose slots and can be booked. INFO_ONLY ones are
    # directory entries visited at their workplace.
    listingType: str = "BOOKABLE"
    clinic: ClinicBrief | None = None

    # Home-visit coverage, for the map. Null until geocoded.
    latitude: float | None = None
    longitude: float | None = None
    serviceRadiusKm: int | None = None

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
    content: str
    files: list[str]
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
