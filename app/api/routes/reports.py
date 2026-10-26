from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.responses import errors
from app.api.dependencies.reports import ReportScopeDependency
from app.api.dependencies.permissions import DbSession
from app.application.dto.reports import ReportGroupBy, VisitReportFilters, VisitReportResponse, VisitReportSummaryResponse
from app.application.services.reports import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/visits", response_model=VisitReportResponse, responses=errors(401, 403, 404, 422))
def report_visits(
    scope: ReportScopeDependency,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: str | None = None,
    reason_id: int | None = None,
    visitor_id: int | None = None,
    registered_by_user_id: int | None = None,
    branch_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
) -> VisitReportResponse:
    filters = VisitReportFilters(
        date_from=date_from,
        date_to=date_to,
        status=status,
        reason_id=reason_id,
        visitor_id=visitor_id,
        registered_by_user_id=registered_by_user_id,
        branch_id=branch_id,
        search=search,
    )
    items, total = ReportService(db).detailed_visits(scope, filters, page=page, page_size=page_size)
    return VisitReportResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/visits/summary", response_model=VisitReportSummaryResponse, responses=errors(401, 403, 404, 422))
def report_visits_summary(
    scope: ReportScopeDependency,
    db: DbSession,
    group_by: ReportGroupBy = Query(...),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: str | None = None,
    reason_id: int | None = None,
    visitor_id: int | None = None,
    registered_by_user_id: int | None = None,
    branch_id: int | None = None,
    search: str | None = Query(default=None, max_length=100),
) -> VisitReportSummaryResponse:
    filters = VisitReportFilters(
        date_from=date_from,
        date_to=date_to,
        status=status,
        reason_id=reason_id,
        visitor_id=visitor_id,
        registered_by_user_id=registered_by_user_id,
        branch_id=branch_id,
        search=search,
    )
    return VisitReportSummaryResponse(group_by=group_by, items=ReportService(db).grouped_visits(scope, filters, group_by))
