from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VisitCreate(BaseModel):
    visitor_id: int
    reason_id: int
    entry_at: datetime | None = None
    destination: str | None = Field(default=None, max_length=200)
    visited_person: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    model_config = ConfigDict(extra="forbid")


class VisitUpdate(BaseModel):
    reason_id: int | None = None
    destination: str | None = Field(default=None, max_length=200)
    visited_person: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    model_config = ConfigDict(extra="forbid")


class VisitCompleteRequest(BaseModel):
    exit_at: datetime | None = None
    model_config = ConfigDict(extra="forbid")


class VisitCancelRequest(BaseModel):
    cancellation_reason: str = Field(min_length=1, max_length=500)
    model_config = ConfigDict(extra="forbid")


class VisitVisitorResponse(BaseModel):
    id: int
    identification: str | None
    first_name: str
    last_name: str
    company: str | None


class VisitBranchResponse(BaseModel):
    id: int
    code: str
    name: str


class VisitUserResponse(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str


class VisitReasonResponse(BaseModel):
    id: int
    code: str
    name: str


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visitor: VisitVisitorResponse
    branch: VisitBranchResponse
    registered_by: VisitUserResponse
    entry_at: datetime
    exit_at: datetime | None
    reason: VisitReasonResponse
    destination: str | None
    visited_person: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    completed_by: VisitUserResponse | None
    cancelled_by: VisitUserResponse | None
    cancelled_at: datetime | None
    cancellation_reason: str | None


class VisitListResponse(BaseModel):
    items: list[VisitResponse]
    total: int
    page: int
    page_size: int
