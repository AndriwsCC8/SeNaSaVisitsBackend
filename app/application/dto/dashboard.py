from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from app.application.dto.common import UtcDatetime


class DashboardSummaryResponse(BaseModel):
    scope: str
    branch_id: int | None
    date_from: UtcDatetime | None
    date_to: UtcDatetime | None
    total_visits: int
    active_visits: int
    completed_visits: int
    cancelled_visits: int
    unique_visitors: int


class DashboardDayPoint(BaseModel):
    date: date
    total: int


class DashboardDaySeriesResponse(BaseModel):
    scope: str
    branch_id: int | None
    items: list[DashboardDayPoint]


class DashboardBucket(BaseModel):
    code: str
    label: str
    total: int


class DashboardDistributionResponse(BaseModel):
    scope: str
    branch_id: int | None
    items: list[DashboardBucket]
