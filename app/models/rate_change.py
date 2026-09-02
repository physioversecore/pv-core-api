from pydantic import BaseModel, Field


class RateChangeRequestCreate(BaseModel):
    rate_to: float = Field(gt=0, description="Requested per-session fee (NPR)")
    reason: str = Field(min_length=10, description="Justification for admin review")


class RateChangeRequestResponse(BaseModel):
    id: str
    therapistId: str
    therapistName: str | None = None
    therapistEmail: str | None = None
    rateFrom: float
    rateTo: float
    reason: str
    status: str
    adminNotes: str | None = None
    createdAt: str


class RateChangeListResponse(BaseModel):
    items: list[RateChangeRequestResponse]
    total: int