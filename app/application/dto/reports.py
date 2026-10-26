from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from app.application.dto.common import UtcDatetime

from app.application.dto.visits import VisitBranchResponse, VisitReasonResponse, VisitUserResponse, VisitVisitorResponse


class ReportGroupBy(str, Enum):
    STATUS = "status"
    REASON = "reason"
    REGISTERED_BY = "registered_by"
    BRANCH = "branch"


class VisitReportFilters(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    status: str | None = None
    reason_id: int | None = None
    visitor_id: int | None = None
    registered_by_user_id: int | None = None
    branch_id: int | None = None
    search: str | None = Field(default=None, max_length=100)


class VisitReportItem(BaseModel):
    id: int
    entry_at: UtcDatetime
    exit_at: UtcDatetime | None
    status: str
    destination: str | None
    visited_person: str | None
    notes: str | None
    visitor: VisitVisitorResponse
    branch: VisitBranchResponse
    reason: VisitReasonResponse
    registered_by: VisitUserResponse
    completed_by_user_id: int | None
    cancelled_by_user_id: int | None
    cancelled_at: UtcDatetime | None
    cancellation_reason: str | None


class VisitReportResponse(BaseModel):
    items: list[VisitReportItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReportGroupItem(BaseModel):
    code: str
    label: str
    total: int


class VisitReportSummaryResponse(BaseModel):
    group_by: ReportGroupBy
    items: list[ReportGroupItem]
