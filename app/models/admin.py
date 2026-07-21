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
