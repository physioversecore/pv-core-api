from datetime import datetime

from pydantic import BaseModel


class PackageCreate(BaseModel):
    name: str
    tag: str
    icon: str = "Brain"
    price: int
    cadence: str
    blurb: str
    points: list[str]
    featured: bool = False
    sortOrder: int = 0
    isActive: bool = True


class PackageUpdate(BaseModel):
    name: str | None = None
    tag: str | None = None
    icon: str | None = None
    price: int | None = None
    cadence: str | None = None
    blurb: str | None = None
    points: list[str] | None = None
    featured: bool | None = None
    sortOrder: int | None = None
    isActive: bool | None = None


class PackageResponse(BaseModel):
    id: str
    name: str
    tag: str
    icon: str
    price: int
    cadence: str
    blurb: str
    points: list[str]
    featured: bool
    sortOrder: int
    isActive: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class PackageListResponse(BaseModel):
    packages: list[PackageResponse]
    total: int
