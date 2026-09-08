from datetime import datetime

from pydantic import BaseModel


class PackagePurchaseRequest(BaseModel):
    paymentMethod: str = "CASH"


class PackagePurchaseResponse(BaseModel):
    id: str
    userId: str
    packageId: str
    packageName: str
    packageTag: str
    sessionsTotal: int
    sessionsUsed: int
    sessionsRemaining: int
    status: str
    purchasedAt: datetime
    expiresAt: datetime
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class PackagePurchaseDetailResponse(PackagePurchaseResponse):
    payment: dict | None = None
    sessions: list[dict] = []


class PackagePurchaseListResponse(BaseModel):
    purchases: list[PackagePurchaseResponse]
    total: int


class AdminPackagePurchaseResponse(BaseModel):
    id: str
    patientName: str
    patientId: str
    packageName: str
    packageId: str
    sessionsTotal: int
    sessionsUsed: int
    sessionsRemaining: int
    status: str
    amount: float
    purchasedAt: str
    expiresAt: str

    class Config:
        from_attributes = True


class AdminPackageStatsResponse(BaseModel):
    totalRevenue: float
    activePurchases: int
    totalPurchases: int
    sessionsDelivered: int
    mostPopularPackage: str | None = None


class PackagePurchaseListAdminResponse(BaseModel):
    purchases: list[AdminPackagePurchaseResponse]
    total: int
