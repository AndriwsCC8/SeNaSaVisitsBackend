from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Date, case, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.infrastructure.persistence.models import Visit, VisitReason


@dataclass(frozen=True)
class DashboardScope:
    branch_id: int | None
    is_global: bool

    @property
    def label(self) -> str:
        return "global" if self.is_global else "branch"


class DashboardService:
    """SQL-first aggregate queries for the operational dashboard."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(
        self,
        scope: DashboardScope,
        date_from: date | datetime | None = None,
        date_to: date | datetime | None = None,
    ) -> dict[str, int | str | date | None]:
        filters = self._filters(scope, date_from, date_to)
        row = self.db.execute(
            select(
                func.count(Visit.id).label("total_visits"),
                func.coalesce(func.sum(case((Visit.status == "ACTIVE", 1), else_=0)), 0).label("active_visits"),
                func.coalesce(func.sum(case((Visit.status == "COMPLETED", 1), else_=0)), 0).label("completed_visits"),
                func.coalesce(func.sum(case((Visit.status == "CANCELLED", 1), else_=0)), 0).label("cancelled_visits"),
                func.count(func.distinct(Visit.visitor_id)).label("unique_visitors"),
            ).where(*filters)
        ).one()
        return {
            "scope": scope.label,
            "branch_id": scope.branch_id,
            "date_from": self._response_datetime(date_from),
            "date_to": self._response_datetime(date_to),
            "total_visits": int(row.total_visits or 0),
            "active_visits": int(row.active_visits or 0),
            "completed_visits": int(row.completed_visits or 0),
            "cancelled_visits": int(row.cancelled_visits or 0),
            "unique_visitors": int(row.unique_visitors or 0),
        }

    def visits_by_day(
        self,
        scope: DashboardScope,
        date_from: date | datetime | None = None,
        date_to: date | datetime | None = None,
    ) -> list[dict[str, date | int]]:
        rows = self.db.execute(
            select(
                func.cast(Visit.entry_at, Date).label("visit_date"),
                func.count(Visit.id).label("total"),
            )
            .where(*self._filters(scope, date_from, date_to))
            .group_by(func.cast(Visit.entry_at, Date))
            .order_by(func.cast(Visit.entry_at, Date))
        ).all()
        return [{"date": row.visit_date, "total": int(row.total)} for row in rows]

    def visits_by_status(
        self,
        scope: DashboardScope,
        date_from: date | datetime | None = None,
        date_to: date | datetime | None = None,
    ) -> list[dict[str, str | int]]:
        rows = self.db.execute(
            select(Visit.status.label("code"), func.count(Visit.id).label("total"))
            .where(*self._filters(scope, date_from, date_to))
            .group_by(Visit.status)
            .order_by(Visit.status)
        ).all()
        return [{"code": row.code, "label": row.code, "total": int(row.total)} for row in rows]

    def visits_by_reason(
        self,
        scope: DashboardScope,
        date_from: date | datetime | None = None,
        date_to: date | datetime | None = None,
    ) -> list[dict[str, str | int]]:
        rows = self.db.execute(
            select(
                VisitReason.code.label("code"),
                VisitReason.name.label("label"),
                func.count(Visit.id).label("total"),
            )
            .join(VisitReason, VisitReason.id == Visit.reason_id)
            .where(*self._filters(scope, date_from, date_to))
            .group_by(VisitReason.code, VisitReason.name)
            .order_by(VisitReason.name)
        ).all()
        return [{"code": row.code, "label": row.label, "total": int(row.total)} for row in rows]

    @staticmethod
    def _filters(scope: DashboardScope, date_from: date | datetime | None, date_to: date | datetime | None):
        if date_from is not None and date_to is not None and date_to < date_from:
            raise ValidationError("date_to no puede ser anterior a date_from.")
        filters = []
        if not scope.is_global:
            if scope.branch_id is None:
                raise ValidationError("El contexto de sucursal no es válido.")
            filters.append(Visit.branch_id == scope.branch_id)
        if date_from is not None:
            filters.append(Visit.entry_at >= DashboardService._start_datetime(date_from))
        if date_to is not None:
            filters.append(Visit.entry_at < DashboardService._end_datetime(date_to))
        return filters

    @staticmethod
    def _start_datetime(value: date | datetime) -> datetime:
        if isinstance(value, datetime):
            return DashboardService._utc_naive(value)
        return datetime.combine(value, time.min)

    @staticmethod
    def _end_datetime(value: date | datetime) -> datetime:
        if isinstance(value, datetime):
            return DashboardService._utc_naive(value)
        return datetime.combine(value + timedelta(days=1), time.min)

    @staticmethod
    def _response_datetime(value: date | datetime | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return datetime.combine(value, time.min, tzinfo=timezone.utc)

    @staticmethod
    def _utc_naive(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
