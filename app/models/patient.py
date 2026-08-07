from datetime import date

from pydantic import BaseModel, field_validator


CITIES = ["Kathmandu", "Lalitpur", "Bhaktapur", "Pokhara", "Chitwan", "Biratnagar"]
GENDER_OPTIONS = ["Any", "Male", "Female"]


class PatientProfileResponse(BaseModel):
    id: str
    userId: str
    name: str
    phone: str
    city: str
    address: str | None = None
    history: str | None = None
    dob: str | None = None
    age: int | None = None
    gender: str = "Any"
    condition: str | None = None
    emergencyName: str | None = None
    emergencyRelation: str | None = None
    emergencyPhone: str | None = None
    notifEmail: bool = True
    notifSms: bool = False
    createdAt: str
    updatedAt: str

    class Config:
        from_attributes = True


class PatientProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    city: str | None = None
    address: str | None = None
    history: str | None = None
    dob: str | None = None
    gender: str | None = None
    emergencyName: str | None = None
    emergencyRelation: str | None = None
    emergencyPhone: str | None = None
    notifEmail: bool | None = None
    notifSms: bool | None = None

    @field_validator("phone", "emergencyPhone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Phone number must have 7-15 digits")
        return v

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("Date of birth must be a valid date (YYYY-MM-DD)") from exc
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in GENDER_OPTIONS:
            raise ValueError(f"Gender must be one of: {', '.join(GENDER_OPTIONS)}")
        return v

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in CITIES:
            raise ValueError(f"City must be one of: {', '.join(CITIES)}")
        return v


class NextSessionInfo(BaseModel):
    id: str
    therapistName: str
    therapistId: str
    date: str
    time: str
    type: str
    status: str


class PatientDashboardResponse(BaseModel):
    name: str
    totalSessions: int
    completedSessions: int
    upcomingSessions: int
    nextSession: NextSessionInfo | None = None
    referralCode: str
    referralLink: str

    class Config:
        from_attributes = True


class ReferralResponse(BaseModel):
    code: str
    link: str
