from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.application.dto.visits import VisitCancelRequest, VisitCompleteRequest, VisitCreate, VisitUpdate
from app.application.services.audit import AuditContext, AuditService
from app.application.services.branch_access import BranchContext
from app.application.validators.visitors import normalize_required_text
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.persistence.models import Branch, User, Visit, VisitReason, Visitor


class VisitManagementService:
    """Application service for branch-owned historical visits."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_visits(
        self,
        context: BranchContext,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        visitor_id: int | None = None,
        reason_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        search: str | None = None,
    ) -> tuple[list[Visit], int]:
        query, filters = self._scoped_query(context)
        if status is not None:
            self._validate_status(status)
            filters.append(Visit.status == status)
        if visitor_id is not None:
            filters.append(Visit.visitor_id == visitor_id)
        if reason_id is not None:
            filters.append(Visit.reason_id == reason_id)
        if date_from is not None:
            filters.append(Visit.entry_at >= self._utc_naive(date_from))
        if date_to is not None:
            filters.append(Visit.entry_at < self._utc_naive(date_to))
        if search:
            pattern = f"%{search.strip()}%"
            query = query.join(Visitor, Visitor.id == Visit.visitor_id)
            filters.append(
                or_(
                    Visitor.identification_normalized.like(pattern),
                    Visitor.first_name.like(pattern),
                    Visitor.last_name.like(pattern),
                    Visitor.company.like(pattern),
                    Visit.destination.like(pattern),
                    Visit.visited_person.like(pattern),
                )
            )
        total = self.db.scalar(
            select(func.count(Visit.id))
            .join(Visitor, Visitor.id == Visit.visitor_id)
            .where(*filters)
        ) or 0
        visits = list(
            self.db.scalars(
                query.where(*filters)
                .order_by(Visit.entry_at.desc(), Visit.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).unique().all()
        )
        return visits, total

    def get_visit(self, context: BranchContext, visit_id: int) -> Visit:
        query, filters = self._scoped_query(context)
        visit = self.db.scalar(query.where(*filters, Visit.id == visit_id))
        if visit is None:
            raise NotFoundError("La visita solicitada no existe.")
        return visit

    def create_visit(self, context: BranchContext, user_id: int, payload: VisitCreate, audit: AuditContext | None = None) -> Visit:
        visitor = self.db.scalar(select(Visitor).where(Visitor.id == payload.visitor_id))
        if visitor is None:
            raise NotFoundError("El visitante solicitado no existe.")
        if not visitor.is_active:
            raise ValidationError("El visitante solicitado está inactivo.")
        reason = self.db.scalar(select(VisitReason).where(VisitReason.id == payload.reason_id))
        if reason is None:
            raise NotFoundError("El motivo de visita solicitado no existe.")
        if not reason.is_active:
            raise ValidationError("El motivo de visita solicitado está inactivo.")
        entry_at = self._utc_naive(payload.entry_at)
        visit = Visit(
            visitor_id=payload.visitor_id,
            branch_id=context.branch_id,
            registered_by_user_id=user_id,
            entry_at=entry_at,
            exit_at=None,
            reason_id=payload.reason_id,
            destination=self._optional_text(payload.destination),
            visited_person=self._optional_text(payload.visited_person),
            status="ACTIVE",
            notes=self._optional_text(payload.notes),
        )
        try:
            self.db.add(visit)
            self.db.flush()
            AuditService(self.db).record(actor_user_id=user_id, action="CREATE_VISIT", entity_type="Visit", entity_id=visit.id, branch_id=context.branch_id, new_values={"visit_id": visit.id, "visitor_id": visit.visitor_id, "branch_id": visit.branch_id, "reason_id": visit.reason_id, "entry_at": visit.entry_at, "destination": visit.destination}, **(audit.__dict__ if audit else {}))
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("No se pudo crear la visita por un conflicto de integridad.") from exc
        return self.get_visit(context, visit.id)

    def update_visit(self, context: BranchContext, visit_id: int, payload: VisitUpdate, actor_id: int | None = None, audit: AuditContext | None = None) -> Visit:
        visit = self.get_visit(context, visit_id)
        if visit.status != "ACTIVE":
            raise ConflictError("Solo se pueden modificar visitas activas.")
        fields = payload.model_fields_set
        old_values = {}
        new_values = {}
        if "reason_id" in fields:
            if payload.reason_id is None:
                raise ValidationError("ReasonId no puede ser null.")
            reason = self.db.scalar(select(VisitReason).where(VisitReason.id == payload.reason_id))
            if reason is None:
                raise NotFoundError("El motivo de visita solicitado no existe.")
            if not reason.is_active:
                raise ValidationError("El motivo de visita solicitado está inactivo.")
            old_values["reason_id"] = visit.reason_id
            visit.reason_id = payload.reason_id
            new_values["reason_id"] = visit.reason_id
        if "destination" in fields:
            old_values["destination"] = visit.destination
            visit.destination = self._optional_text(payload.destination)
            new_values["destination"] = visit.destination
        if "visited_person" in fields:
            old_values["visited_person"] = visit.visited_person
            visit.visited_person = self._optional_text(payload.visited_person)
            new_values["visited_person"] = visit.visited_person
        if "notes" in fields:
            old_values["notes"] = visit.notes
            visit.notes = self._optional_text(payload.notes)
            new_values["notes"] = visit.notes
        if actor_id is not None:
            AuditService(self.db).record(actor_user_id=actor_id, action="UPDATE_VISIT", entity_type="Visit", entity_id=visit.id, branch_id=visit.branch_id, old_values=old_values, new_values=new_values, **(audit.__dict__ if audit else {}))
        self.db.commit()
        return self.get_visit(context, visit_id)

    def complete_visit(self, context: BranchContext, user_id: int, visit_id: int, payload: VisitCompleteRequest, audit: AuditContext | None = None) -> Visit:
        visit = self.get_visit(context, visit_id)
        if visit.status != "ACTIVE":
            raise ConflictError("Solo se pueden completar visitas activas.")
        exit_at = self._utc_naive(payload.exit_at)
        if exit_at < visit.entry_at:
            raise ValidationError("ExitAt no puede ser anterior a EntryAt.")
        visit.status = "COMPLETED"
        visit.exit_at = exit_at
        visit.completed_by_user_id = user_id
        AuditService(self.db).record(actor_user_id=user_id, action="CHECKOUT_VISIT", entity_type="Visit", entity_id=visit.id, branch_id=visit.branch_id, old_values={"status": "ACTIVE"}, new_values={"status": "COMPLETED", "exit_at": exit_at}, **(audit.__dict__ if audit else {}))
        self.db.commit()
        return self.get_visit(context, visit_id)

    def cancel_visit(self, context: BranchContext, user_id: int, visit_id: int, payload: VisitCancelRequest, audit: AuditContext | None = None) -> Visit:
        visit = self.get_visit(context, visit_id)
        if visit.status != "ACTIVE":
            raise ConflictError("Solo se pueden cancelar visitas activas.")
        visit.status = "CANCELLED"
        visit.cancelled_by_user_id = user_id
        visit.cancelled_at = self._utc_naive(None)
        visit.cancellation_reason = normalize_required_text(payload.cancellation_reason, "La razón de cancelación")
        AuditService(self.db).record(actor_user_id=user_id, action="CANCEL_VISIT", entity_type="Visit", entity_id=visit.id, branch_id=visit.branch_id, old_values={"status": "ACTIVE"}, new_values={"status": "CANCELLED", "cancelled_at": visit.cancelled_at, "cancellation_reason": visit.cancellation_reason}, **(audit.__dict__ if audit else {}))
        self.db.commit()
        return self.get_visit(context, visit_id)

    def _scoped_query(self, context: BranchContext):
        query = select(Visit).options(
            selectinload(Visit.visitor),
            selectinload(Visit.branch),
            selectinload(Visit.reason),
            selectinload(Visit.registered_by),
            selectinload(Visit.completed_by),
            selectinload(Visit.cancelled_by),
        )
        return query, [Visit.branch_id == context.branch_id]

    @staticmethod
    def _validate_status(value: str) -> None:
        if value not in {"ACTIVE", "COMPLETED", "CANCELLED"}:
            raise ValidationError("El estado de visita no es válido.")

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @staticmethod
    def _utc_naive(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is not None:
            return current.astimezone(timezone.utc).replace(tzinfo=None)
        return current
