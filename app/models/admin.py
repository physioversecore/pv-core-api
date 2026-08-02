from pydantic import BaseModel, ConfigDict


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class AdminDashboardStats(_CamelModel):
    total_therapists: int
    total_patients: int
    sessions_this_week: int
    pending_verifications: int


class AdminEarningsResponse(_CamelModel):
    platform_earnings: float
    description: str


class AdminRecentActivity(_CamelModel):
    id: str
    patient_name: str
    therapist_name: str
    type: str
    timestamp: str


class AdminTherapistDocument(BaseModel):
    id: str
    documentType: str | None = None
    documentUrl: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    status: str | None = None
    note: str | None = None


class AdminTherapistData(BaseModel):
    id: str
    name: str
    city: str
    specialty: str
    rating: float
    sessions: int
    status: str
    joined: str
    isActive: bool
    phone: str | None = None
    email: str | None = None
    gender: str | None = None
    price: float | None = None
    experience: int | None = None
    bio: str | None = None
    mediaUrls: str | None = None
    documents: list[AdminTherapistDocument] | None = None

    class Config:
        from_attributes = True


class AdminTherapistListResponse(BaseModel):
    items: list[AdminTherapistData]
    total: int


class AdminTherapistUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None
    isActive: bool | None = None


class AdminRejectRequest(BaseModel):
    note: str = ""


class AdminPatientData(BaseModel):
    id: str
    name: str
    city: str
    sessions: int
    therapist: str
    therapistId: str
    joined: str
    isActive: bool
    phone: str | None = None
    email: str | None = None

    class Config:
        from_attributes = True


class AdminPatientListResponse(BaseModel):
    items: list[AdminPatientData]
    total: int


class AdminPatientUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    isActive: bool | None = None


class AdminBookingData(BaseModel):
    id: str
    patient: str
    patientId: str
    patientPhone: str = ""
    therapist: str
    therapistId: str
    therapistPhone: str = ""
    date: str
    originalTime: str
    sessionType: str
    status: str
    paymentStatus: str = ""
    paymentMethod: str = ""

    class Config:
        from_attributes = True


class AdminBookingListResponse(BaseModel):
    items: list[AdminBookingData]
    total: int


class AdminPerformanceData(BaseModel):
    id: str
    name: str
    avgRating: float
    sessions: int
    reviews: int
    trend: float
    linkedComplaints: int
    status: str

    class Config:
        from_attributes = True


class AdminPerformanceListResponse(BaseModel):
    items: list[AdminPerformanceData]
    total: int


class AdminPerformanceUpdate(BaseModel):
    name: str | None = None
    avgRating: float | None = None
    sessions: int | None = None
    reviews: int | None = None
    trend: float | None = None
    linkedComplaints: int | None = None
    status: str | None = None


class ScheduleReviewRequest(BaseModel):
    date: str
    adminId: str
    notes: str = ""


class ResolveRequest(BaseModel):
    note: str = ""
    reviewBy: str = ""


class RemoveFromTeamRequest(BaseModel):
    reason: str = ""


class AdminCreateTherapistRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None
    city: str
    specialty: str
    gender: str
    price: float
    experience: int
    bio: str = ""
    citizenshipNumber: str | None = None
    panNumber: str | None = None
    medicalLicenseUrl: str | None = None
    certificateUrl: str | None = None


class AdminTherapistCreatedResponse(BaseModel):
    id: str
    userId: str
    name: str
    email: str
    phone: str | None = None
    city: str
    specialty: str
    gender: str
    price: float
    experience: int
    bio: str
    createdAt: str
    updatedAt: str
