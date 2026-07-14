from datetime import datetime
from pydantic import BaseModel


class ReportCreate(BaseModel):
    patientId: str
    therapistId: str | None = None
    sessionId: str | None = None
    title: str
    content: str
    fileUrl: str | None = None


class ReportUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    fileUrl: str | None = None


class ReportResponse(BaseModel):
    id: str
    patientId: str
    therapistId: str | None = None
    sessionId: str | None = None
    title: str
    content: str
    fileUrl: str | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True
