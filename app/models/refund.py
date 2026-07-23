from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RefundCreate(BaseModel):
    patientId: str = Field(min_length=1, max_length=64)
    bookingId: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=32)


class RefundUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=16)
    denyReason: str | None = Field(default=None, max_length=2000)


class ManualCaseCreate(BaseModel):
    patientId: str = Field(min_length=1, max_length=64)
    bookingId: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=32)
    assigneeId: Optional[str] = None
    notes: Optional[str] = None
    alsoCreateDispute: bool = False
    disputeCategory: Optional[str] = None
    disputePriority: Optional[str] = "Normal"
    disputeDescription: Optional[str] = None


class ManualCaseResponse(BaseModel):
    refund: dict
    complaint: dict | None = None


class AssignRequest(BaseModel):
    assigneeId: str = Field(min_length=1, max_length=200)


class RefundResponse(BaseModel):
    id: str
    patientId: str
    patient: str
    bookingId: str
    amount: float
    reason: str
    status: str
    denyReason: str | None = None
    resolvedAt: datetime | None = None
    filed: str
    assigneeId: str | None = None
    source: str | None = None
    complaintId: str | None = None
    notes: str | None = None

    class Config:
        from_attributes = True


class RefundListResponse(BaseModel):
    items: list[RefundResponse]
    total: int


class RefundStatsResponse(BaseModel):
    pending: int
    refundedThisMonth: int
    disputeRate: float
    avgResolutionDays: float
