from pydantic import BaseModel


class ServiceAreaCreate(BaseModel):
    name: str
    localities: list[str]
    therapistIds: list[str] | None = None


class ServiceAreaUpdate(BaseModel):
    name: str | None = None
    localities: list[str] | None = None


class ServiceAreaResponse(BaseModel):
    id: str
    name: str
    localities: list[str]
    assignedTherapists: int
    bookingsThisMonth: int
    status: str

    class Config:
        from_attributes = True


class ServiceAreaListResponse(BaseModel):
    items: list[ServiceAreaResponse]
    total: int


class TherapistAssignRequest(BaseModel):
    therapistId: str
