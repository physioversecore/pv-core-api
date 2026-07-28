from pydantic import BaseModel


class ServiceCreate(BaseModel):
    name: str
    description: str
    category: str
    iconName: str = ""
    isActive: bool = True
    sortOrder: int = 0


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    iconName: str | None = None
    isActive: bool | None = None
    sortOrder: int | None = None


class ServiceResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    iconName: str
    isActive: bool
    sortOrder: int

    class Config:
        from_attributes = True


class ServiceListResponse(BaseModel):
    services: list[ServiceResponse]
    total: int
