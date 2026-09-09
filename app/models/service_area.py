from pydantic import BaseModel


class ServiceAreaCreate(BaseModel):
    name: str
    localities: list[str]
    therapistIds: list[str] | None = None

    # Without these the area covers nobody by radius, silently -- coverage
    # then falls back to the explicit therapist/area links alone.
    latitude: float | None = None
    longitude: float | None = None


class ServiceAreaUpdate(BaseModel):
    name: str | None = None
    localities: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None


class ServiceAreaResponse(BaseModel):
    id: str
    name: str
    localities: list[str]
    assignedTherapists: int
    bookingsThisMonth: int
    status: str

    # Null until geocoded. The admin table flags these so an area that
    # silently covers nobody is visible rather than mysterious.
    latitude: float | None = None
    longitude: float | None = None

    class Config:
        from_attributes = True


class ServiceAreaListResponse(BaseModel):
    items: list[ServiceAreaResponse]
    total: int


class TherapistAssignRequest(BaseModel):
    therapistId: str
