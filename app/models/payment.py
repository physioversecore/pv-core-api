from datetime import datetime
from pydantic import BaseModel


class PaymentCreate(BaseModel):
    amount: float
    method: str = "CASH"
    sessionId: str | None = None


class PaymentResponse(BaseModel):
    id: str
    userId: str
    amount: float
    status: str
    method: str
    sessionId: str | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    payments: list[PaymentResponse]
    total: float
