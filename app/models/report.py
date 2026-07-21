from datetime import datetime
from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    patientId: str = Field(min_length=1, max_length=64)
    therapistId: str | None = Field(default=None, max_length=64)
    sessionId: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    fileUrl: str | None = Field(default=None, max_length=4000)


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=10000)
    fileUrl: str | None = Field(default=None, max_length=4000)


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
