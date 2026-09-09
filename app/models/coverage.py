from pydantic import BaseModel, ConfigDict

from app.models.therapist import ClinicBrief


class ServiceAreaBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str

    # Null until the area is geocoded. Coverage then falls back to the
    # explicit admin-managed therapist/area links.
    latitude: float | None = None
    longitude: float | None = None


class ServiceAreaBriefListResponse(BaseModel):
    areas: list[ServiceAreaBrief]


class CoverageTherapist(BaseModel):
    id: str
    name: str
    specialty: str = ""
    city: str = ""
    price: float = 0.0
    listingType: str = "BOOKABLE"
    serviceRadiusKm: int | None = None

    # Null when either side has not been geocoded.
    distanceKm: float | None = None

    # Whether this therapist can actually reach the chosen area, by
    # explicit link or by radius.
    covers: bool = False

    clinic: ClinicBrief | None = None


class CoverageClinic(BaseModel):
    id: str
    name: str
    area: str = ""
    city: str = ""
    address: str = ""
    hours: str = ""
    distanceKm: float | None = None


class CoverageResponse(BaseModel):
    area: ServiceAreaBrief | None = None
    therapists: list[CoverageTherapist]
    clinics: list[CoverageClinic]
    coveringCount: int
