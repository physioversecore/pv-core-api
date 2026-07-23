from datetime import datetime
from pydantic import BaseModel, Field


class ComplaintCreate(BaseModel):
    type: str = Field(min_length=1, max_length=16)
    complainantId: str = Field(min_length=1, max_length=64)
    complainantName: str = Field(min_length=1, max_length=200)
    againstId: str = Field(min_length=1, max_length=64)
    againstName: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    priority: str = Field(default="Normal", max_length=16)
    description: str = Field(min_length=1, max_length=5000)
    bookingId: str | None = Field(default=None, max_length=64)
    evidenceUrls: str | None = Field(default=None, max_length=4000)
    preferredOutcome: str | None = Field(default=None, max_length=200)


class ComplaintUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    priority: str | None = Field(default=None, max_length=16)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    assignee: str | None = Field(default=None, max_length=200)
    adminNotes: str | None = Field(default=None, max_length=5000)


class ComplaintResponse(BaseModel):
    id: str
    type: str
    complainantId: str
    complainantName: str
    againstId: str
    againstName: str
    category: str
    priority: str
    status: str
    description: str
    bookingId: str | None = None
    evidenceUrls: str | None = None
    preferredOutcome: str | None = None
    assignee: str | None = None
    adminNotes: str | None = None
    source: str | None = None
    refundId: str | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class ComplaintListResponse(BaseModel):
    items: list[ComplaintResponse]
    total: int
