from datetime import datetime
from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    amount: float = Field(ge=0, le=1000000)
    method: str = Field(default="CASH", max_length=32)
    sessionId: str | None = Field(default=None, max_length=64)
    currency: str = Field(default="NPR", max_length=8)
    platformFee: float = Field(default=0, ge=0, le=1000000)
    paymentType: str | None = Field(default=None, max_length=32)
    transactionRef: str | None = Field(default=None, max_length=128)
    cardLast4: str | None = Field(default=None, max_length=4)
    walletMobile: str | None = Field(default=None, max_length=20)
    billingCountry: str | None = Field(default=None, max_length=8)


class PaymentResponse(BaseModel):
    id: str
    userId: str
    amount: float
    status: str
    method: str
    sessionId: str | None = None
    currency: str = "NPR"
    platformFee: float = 0
    paymentType: str | None = None
    transactionRef: str | None = None
    cardLast4: str | None = None
    walletMobile: str | None = None
    billingCountry: str | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    payments: list[PaymentResponse]
    total: int


class BookingPaymentRequest(BaseModel):
    therapistId: str = Field(min_length=1, max_length=64)
    date: datetime
    time: str = Field(min_length=1, max_length=10)
    type: str = Field(default="HOME_VISIT", max_length=32)
    address: str = Field(min_length=1, max_length=500)
    fee: float = Field(ge=0, le=1000000)
    notes: str | None = Field(default=None, max_length=2000)
    familyMemberId: str | None = Field(default=None, max_length=64)
    currency: str = Field(default="NPR", max_length=8)
    paymentMethod: str = Field(default="CASH", max_length=32)
    paymentType: str | None = Field(default=None, max_length=32)
    platformFee: float = Field(default=0, ge=0, le=1000000)
    transactionRef: str | None = Field(default=None, max_length=128)
    cardLast4: str | None = Field(default=None, max_length=4)
    walletMobile: str | None = Field(default=None, max_length=20)
    billingCountry: str | None = Field(default=None, max_length=8)


class SessionPaymentResponse(BaseModel):
    id: str
    therapistId: str
    therapistName: str = ""
    patientId: str
    patientName: str = ""
    patientPhone: str = ""
    familyMemberId: str | None = None
    familyMemberName: str | None = None
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


class BookingPaymentResponse(BaseModel):
    session: SessionPaymentResponse
    payment: PaymentResponse
