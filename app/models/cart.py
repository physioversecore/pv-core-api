from datetime import datetime
from pydantic import BaseModel

from app.models.product import ProductResponse


class CartItemCreate(BaseModel):
    productId: str
    type: str = "BUY"
    quantity: int = 1
    rentalDays: int = 7


class CartItemUpdate(BaseModel):
    quantity: int | None = None
    rentalDays: int | None = None
    type: str | None = None


class CartItemResponse(BaseModel):
    id: str
    userId: str
    productId: str
    product: ProductResponse
    type: str
    quantity: int
    rentalDays: int
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total: float
    deliveryFee: float
    grandTotal: float
