from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VisitorTypeResponse(BaseModel):
    id: int
    code: str
    name: str


class VisitorCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    identification: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    company: str | None = Field(default=None, max_length=200)
    visitor_type_id: int | None = None


class VisitorUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    identification: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    company: str | None = Field(default=None, max_length=200)
    visitor_type_id: int | None = None


class VisitorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identification: str | None
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    company: str | None
    visitor_type: VisitorTypeResponse | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VisitorListResponse(BaseModel):
    items: list[VisitorResponse]
    total: int
    page: int
    page_size: int
