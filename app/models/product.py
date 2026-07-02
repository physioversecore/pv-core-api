from datetime import datetime
from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    category: str
    price: float
    rentPerDay: float = 0
    inStock: int = 0
    emoji: str = ""
    description: str | None = None
    imageUrl: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    price: float | None = None
    rentPerDay: float | None = None
    inStock: int | None = None
    emoji: str | None = None
    description: str | None = None
    imageUrl: str | None = None


class ProductResponse(BaseModel):
    id: str
    name: str
    category: str
    price: float
    rentPerDay: float
    inStock: int
    emoji: str
    description: str | None = None
    imageUrl: str | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: list[ProductResponse]
    total: int
