from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import Date, func, or_, select
from sqlalchemy.orm import Session

from app.application.dto.reports import ReportGroupBy, VisitReportFilters
from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.persistence.models import Branch, User, Visit, VisitReason, Visitor


@dataclass(frozen=True)
class ReportScope:
    branch_id: int | None
    is_global: bool


class ReportService:
    """SQL-first historical and grouped visit reports."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def detailed_visits(
        self,
        scope: ReportScope,
        filters: VisitReportFilters,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        self._validate_filters(filters)
        query, predicates = self._base_query(scope, filters)
        total = self.db.scalar(
            select(func.count(Visit.id))
            .select_from(Visit)
            .join(Visitor, Visitor.id == Visit.visitor_id)
            .where(*predicates)
        ) or 0
        rows = self.db.execute(
            query.where(*predicates)
            .order_by(Visit.entry_at.desc(), Visit.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [self._row_to_item(row) for row in rows], int(total)

    def grouped_visits(self, scope: ReportScope, filters: VisitReportFilters, group_by: ReportGroupBy) -> list[dict[str, str | int]]:
        self._validate_filters(filters)
        if group_by == ReportGroupBy.BRANCH and not scope.is_global:
            raise ValidationError("La agrupación por sucursal requiere acceso global.")
        _, predicates = self._base_query(scope, filters)
        if group_by == ReportGroupBy.STATUS:
            code = Visit.status
            label = Visit.status
            query = select(code.label("code"), label.label("label"), func.count(Visit.id).label("total"))
        elif group_by == ReportGroupBy.REASON:
            query = select(VisitReason.code.label("code"), VisitReason.name.label("label"), func.count(Visit.id).label("total")).join(VisitReason, VisitReason.id == Visit.reason_id)
            code, label = VisitReason.code, VisitReason.name
        elif group_by == ReportGroupBy.REGISTERED_BY:
            query = select(User.username.label("code"), (User.first_name + " " + User.last_name).label("label"), func.count(Visit.id).label("total")).join(User, User.id == Visit.registered_by_user_id)
            code, label = User.username, User.first_name + " " + User.last_name
        else:
            query = select(Branch.code.label("code"), Branch.name.label("label"), func.count(Visit.id).label("total")).join(Branch, Branch.id == Visit.branch_id)
            code, label = Branch.code, Branch.name
        rows = self.db.execute(query.select_from(Visit).where(*predicates).group_by(code, label)).all()
        return [{"code": row.code, "label": row.label, "total": int(row.total)} for row in rows]

    def _base_query(self, scope: ReportScope, filters: VisitReportFilters):
        query = select(
            Visit.id,
            Visit.entry_at,
            Visit.exit_at,
            Visit.status,
            Visit.destination,
            Visit.visited_person,
            Visit.notes,
            Visit.completed_by_user_id,
            Visit.cancelled_by_user_id,
            Visit.cancelled_at,
            Visit.cancellation_reason,
            Visitor.id.label("visitor_id"),
            Visitor.identification,
            Visitor.first_name.label("visitor_first_name"),
            Visitor.last_name.label("visitor_last_name"),
            Visitor.company,
            Branch.id.label("branch_id"),
            Branch.code.label("branch_code"),
            Branch.name.label("branch_name"),
            VisitReason.id.label("reason_id"),
            VisitReason.code.label("reason_code"),
            VisitReason.name.label("reason_name"),
            User.id.label("registered_by_id"),
            User.username,
            User.first_name.label("registered_first_name"),
            User.last_name.label("registered_last_name"),
        ).join(Visitor, Visitor.id == Visit.visitor_id).join(Branch, Branch.id == Visit.branch_id).join(VisitReason, VisitReason.id == Visit.reason_id).join(User, User.id == Visit.registered_by_user_id)
        predicates = []
        if scope.branch_id is not None:
            predicates.append(Visit.branch_id == scope.branch_id)
        if filters.branch_id is not None:
            predicates.append(Visit.branch_id == filters.branch_id)
        if filters.status is not None:
            if filters.status not in {"ACTIVE", "COMPLETED", "CANCELLED"}:
                raise ValidationError("El estado de visita no es válido.")
            predicates.append(Visit.status == filters.status)
        if filters.reason_id is not None:
            if self.db.scalar(select(VisitReason.id).where(VisitReason.id == filters.reason_id)) is None:
                raise NotFoundError("El motivo de visita solicitado no existe.")
            predicates.append(Visit.reason_id == filters.reason_id)
        if filters.visitor_id is not None:
            if self.db.scalar(select(Visitor.id).where(Visitor.id == filters.visitor_id)) is None:
                raise NotFoundError("El visitante solicitado no existe.")
            predicates.append(Visit.visitor_id == filters.visitor_id)
        if filters.registered_by_user_id is not None:
            if self.db.scalar(select(User.id).where(User.id == filters.registered_by_user_id)) is None:
                raise NotFoundError("El usuario solicitado no existe.")
            predicates.append(Visit.registered_by_user_id == filters.registered_by_user_id)
        if filters.date_from is not None:
            predicates.append(Visit.entry_at >= self._utc_naive(filters.date_from))
        if filters.date_to is not None:
            predicates.append(Visit.entry_at < self._utc_naive(filters.date_to))
        if filters.search:
            pattern = f"%{filters.search.strip()}%"
            predicates.append(or_(Visitor.identification_normalized.like(pattern), Visitor.first_name.like(pattern), Visitor.last_name.like(pattern), Visitor.company.like(pattern), Visit.destination.like(pattern), Visit.visited_person.like(pattern)))
        return query, predicates

    @staticmethod
    def _row_to_item(row) -> dict:
        return {
            "id": row.id,
            "entry_at": row.entry_at,
            "exit_at": row.exit_at,
            "status": row.status,
            "destination": row.destination,
            "visited_person": row.visited_person,
            "notes": row.notes,
            "visitor": {"id": row.visitor_id, "identification": ReportService._mask(row.identification), "first_name": row.visitor_first_name, "last_name": row.visitor_last_name, "company": row.company},
            "branch": {"id": row.branch_id, "code": row.branch_code, "name": row.branch_name},
            "reason": {"id": row.reason_id, "code": row.reason_code, "name": row.reason_name},
            "registered_by": {"id": row.registered_by_id, "username": row.username, "first_name": row.registered_first_name, "last_name": row.registered_last_name},
            "completed_by_user_id": row.completed_by_user_id,
            "cancelled_by_user_id": row.cancelled_by_user_id,
            "cancelled_at": row.cancelled_at,
            "cancellation_reason": row.cancellation_reason,
        }

    @staticmethod
    def _validate_filters(filters: VisitReportFilters) -> None:
        if filters.date_from and filters.date_to and filters.date_from >= filters.date_to:
            raise ValidationError("date_to debe ser posterior a date_from; el límite superior es exclusivo.")

    @staticmethod
    def _mask(value: str | None) -> str | None:
        if not value:
            return None
        return value[:3] + "***" + value[-4:] if len(value) > 7 else "***"

    @staticmethod
    def _utc_naive(value: datetime) -> datetime:
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
