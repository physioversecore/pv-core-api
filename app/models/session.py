from datetime import datetime
from pydantic import BaseModel


class SessionCreate(BaseModel):
    therapistId: str
    date: datetime
    time: str
    type: str = "HOME_VISIT"
    address: str
    fee: float
    notes: str | None = None


class SessionUpdate(BaseModel):
    status: str | None = None
    date: datetime | None = None
    time: str | None = None
    notes: str | None = None


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
