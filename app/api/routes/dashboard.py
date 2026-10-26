from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.responses import errors
from app.api.dependencies.dashboard import DashboardScopeDependency
from app.api.dependencies.permissions import DbSession
from app.application.dto.dashboard import (
    DashboardDistributionResponse,
    DashboardDaySeriesResponse,
    DashboardSummaryResponse,
)
from app.application.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse, responses=errors(401, 403, 422))
def dashboard_summary(
    scope: DashboardScopeDependency,
    db: DbSession,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(**DashboardService(db).summary(scope, date_from, date_to))


@router.get("/visits-by-day", response_model=DashboardDaySeriesResponse, responses=errors(401, 403, 422))
def dashboard_visits_by_day(
    scope: DashboardScopeDependency,
    db: DbSession,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> DashboardDaySeriesResponse:
    return DashboardDaySeriesResponse(scope=scope.label, branch_id=scope.branch_id, items=DashboardService(db).visits_by_day(scope, date_from, date_to))


@router.get("/visits-by-status", response_model=DashboardDistributionResponse, responses=errors(401, 403, 422))
def dashboard_visits_by_status(
    scope: DashboardScopeDependency,
    db: DbSession,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> DashboardDistributionResponse:
    return DashboardDistributionResponse(scope=scope.label, branch_id=scope.branch_id, items=DashboardService(db).visits_by_status(scope, date_from, date_to))


@router.get("/visits-by-reason", response_model=DashboardDistributionResponse, responses=errors(401, 403, 422))
def dashboard_visits_by_reason(
    scope: DashboardScopeDependency,
    db: DbSession,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> DashboardDistributionResponse:
    return DashboardDistributionResponse(scope=scope.label, branch_id=scope.branch_id, items=DashboardService(db).visits_by_reason(scope, date_from, date_to))
