from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    body: str
    readAt: datetime | None = None
    refType: str | None = None
    refId: str | None = None
    createdAt: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread: int


class NotificationCreate(BaseModel):
    """Admin/system-side creation."""

    userId: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    refType: str | None = Field(default=None, max_length=32)
    refId: str | None = Field(default=None, max_length=64)
