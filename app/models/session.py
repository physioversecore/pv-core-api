from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    therapistId: str = Field(min_length=1, max_length=64)
    date: datetime
    time: str = Field(min_length=1, max_length=10)
    type: str = Field(default="HOME_VISIT", max_length=32)
    address: str = Field(min_length=1, max_length=500)
    fee: float = Field(ge=0, le=1000000)
    notes: str | None = Field(default=None, max_length=2000)


class SessionUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    date: datetime | None = None
    time: str | None = Field(default=None, max_length=10)
    notes: str | None = Field(default=None, max_length=2000)


class SessionResponse(BaseModel):
    id: str
    therapistId: str
    therapistName: str = ""
    patientId: str
    patientName: str = ""
    patientPhone: str = ""
    date: datetime
    time: str
    type: str
    status: str
    address: str
    fee: float
    notes: str | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class RescheduleRequest(BaseModel):
    newDate: str = Field(min_length=1, max_length=20)
    newTime: str = Field(min_length=1, max_length=10)
