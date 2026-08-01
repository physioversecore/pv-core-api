from datetime import datetime
from pydantic import BaseModel, Field


class VerificationCreate(BaseModel):
    therapistId: str
    documentType: str = Field(..., max_length=64)
    documentUrl: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    expires: str | None = None
    severity: str | None = Field(default=None, max_length=16)
    reportedBy: str | None = None
    phone: str | None = None


class VerificationUpdate(BaseModel):
    documentType: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, max_length=32)
    severity: str | None = Field(default=None, max_length=16)
    expires: str | None = None


class VerificationResponse(BaseModel):
    id: str
    therapistId: str
    therapist: str
    documentType: str
    documentUrl: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    uploaded: datetime
    expires: datetime | None = None
    status: str
    severity: str | None = None
    reportedBy: str | None = None
    phone: str | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class VerificationListResponse(BaseModel):
    items: list[VerificationResponse]
    total: int
