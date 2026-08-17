from datetime import datetime

from pydantic import BaseModel


class ClinicCreate(BaseModel):
    name: str
    area: str
    city: str
    address: str
    services: list[str]
    phone: str
    hours: str


class ClinicUpdate(BaseModel):
    name: str | None = None
    area: str | None = None
    city: str | None = None
    address: str | None = None
    services: list[str] | None = None
    phone: str | None = None
    hours: str | None = None


class ClinicResponse(BaseModel):
    id: str
    name: str
    area: str
    city: str
    address: str
    services: list[str]
    phone: str
    hours: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class ClinicListResponse(BaseModel):
    clinics: list[ClinicResponse]
    total: int
