from datetime import datetime
from pydantic import BaseModel


class PaymentCreate(BaseModel):
    amount: float
    method: str = "CASH"
    sessionId: str | None = None
    currency: str = "NPR"
    platformFee: float = 0
    paymentType: str | None = None
    transactionRef: str | None = None
    cardLast4: str | None = None
    walletMobile: str | None = None
    billingCountry: str | None = None


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
    therapistId: str
    date: datetime
    time: str
    type: str = "HOME_VISIT"
    address: str
    fee: float
    notes: str | None = None
    currency: str = "NPR"
    paymentMethod: str = "CASH"
    paymentType: str | None = None
    platformFee: float = 0
    transactionRef: str | None = None
    cardLast4: str | None = None
    walletMobile: str | None = None
    billingCountry: str | None = None


class SessionPaymentResponse(BaseModel):
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


class BookingPaymentResponse(BaseModel):
    session: SessionPaymentResponse
    payment: PaymentResponse
