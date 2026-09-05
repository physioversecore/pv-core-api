from pydantic import BaseModel


class OnboardingStatusResponse(BaseModel):
    completed: bool
    step: str | None = None

    class Config:
        from_attributes = True


class OnboardingCompleteRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    city: str | None = None
    address: str | None = None
    dob: str | None = None
    gender: str | None = None
    condition: str | None = None
    medicalHistory: str | None = None
    emergencyName: str | None = None
    emergencyRelation: str | None = None
    emergencyPhone: str | None = None
    password: str | None = None


class ApplicationSectionFeedback(BaseModel):
    section: str
    message: str


class ApplicationStatusResponse(BaseModel):
    status: str
    feedback: list[ApplicationSectionFeedback] = []

    class Config:
        from_attributes = True
