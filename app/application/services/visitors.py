from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.application.dto.visitors import VisitorCreate, VisitorUpdate
from app.application.services.audit import AuditContext, AuditService
from app.application.validators.visitors import (
    normalize_identification,
    normalize_required_text,
    validate_email,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.infrastructure.persistence.models import Visitor, VisitorType


class VisitorManagementService:
    """Application service for global visitor profiles."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_visitors(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
        visitor_type_id: int | None = None,
        include_contact: bool = False,
    ) -> tuple[list[Visitor], int]:
        query = select(Visitor).options(selectinload(Visitor.visitor_type))
        count_query = select(func.count(Visitor.id)).select_from(Visitor)
        filters = []
        if search:
            pattern = f"%{search.strip()}%"
            columns = [
                Visitor.first_name.like(pattern),
                Visitor.last_name.like(pattern),
                Visitor.identification_normalized.like(pattern),
                Visitor.company.like(pattern),
            ]
            # Protected contact data must not influence results for users without VIEW_VISITOR_CONTACT.
            if include_contact:
                columns += [Visitor.email.like(pattern), Visitor.phone.like(pattern)]
            filters.append(or_(*columns))
        if is_active is not None:
            filters.append(Visitor.is_active.is_(is_active))
        if visitor_type_id is not None:
            filters.append(Visitor.visitor_type_id == visitor_type_id)
        total = self.db.scalar(count_query.where(*filters)) or 0
        visitors = list(
            self.db.scalars(
                query.where(*filters)
                .order_by(Visitor.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).unique().all()
        )
        return visitors, total

    def get_visitor(self, visitor_id: int) -> Visitor:
        visitor = self.db.scalar(
            select(Visitor)
            .options(selectinload(Visitor.visitor_type))
            .where(Visitor.id == visitor_id)
        )
        if visitor is None:
            raise NotFoundError("El visitante solicitado no existe.")
        return visitor

    def create_visitor(self, payload: VisitorCreate, actor_id: int | None = None, audit: AuditContext | None = None) -> Visitor:
        identification_normalized = normalize_identification(payload.identification)
        self._validate_visitor_type(payload.visitor_type_id)
        self._ensure_identification_available(identification_normalized)
        visitor = Visitor(
            first_name=normalize_required_text(payload.first_name, "El nombre"),
            last_name=normalize_required_text(payload.last_name, "El apellido"),
            identification=payload.identification.strip() if payload.identification else None,
            identification_normalized=identification_normalized,
            phone=payload.phone.strip() if payload.phone else None,
            email=validate_email(payload.email),
            company=payload.company.strip() if payload.company else None,
            visitor_type_id=payload.visitor_type_id,
            is_active=True,
        )
        try:
            self.db.add(visitor)
            self.db.flush()
            if actor_id is not None:
                AuditService(self.db).record(actor_user_id=actor_id, action="CREATE_VISITOR", entity_type="Visitor", entity_id=visitor.id, new_values={"visitor_id": visitor.id, "first_name": visitor.first_name, "last_name": visitor.last_name, "is_active": True}, **(audit.__dict__ if audit else {}))
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("La identificación ya está registrada.") from exc
        return self.get_visitor(visitor.id)

    def update_visitor(self, visitor_id: int, payload: VisitorUpdate, actor_id: int | None = None, audit: AuditContext | None = None) -> Visitor:
        visitor = self.get_visitor(visitor_id)
        identification_normalized = normalize_identification(payload.identification)
        self._validate_visitor_type(payload.visitor_type_id)
        if identification_normalized != visitor.identification_normalized:
            self._ensure_identification_available(identification_normalized, excluding_id=visitor_id)
        fields_set = payload.model_fields_set
        old_values = {}
        new_values = {}
        if "first_name" in fields_set and payload.first_name is not None:
            old_values["first_name"] = visitor.first_name
            visitor.first_name = normalize_required_text(payload.first_name, "El nombre")
            new_values["first_name"] = visitor.first_name
        if "last_name" in fields_set and payload.last_name is not None:
            old_values["last_name"] = visitor.last_name
            visitor.last_name = normalize_required_text(payload.last_name, "El apellido")
            new_values["last_name"] = visitor.last_name
        if "identification" in fields_set:
            visitor.identification = payload.identification.strip() if payload.identification else None
            visitor.identification_normalized = identification_normalized
            old_values["identification"] = "[REDACTED]"
            new_values["identification"] = "[REDACTED]" if visitor.identification else None
        if "phone" in fields_set:
            visitor.phone = payload.phone.strip() or None
        if "email" in fields_set:
            visitor.email = validate_email(payload.email)
        if "company" in fields_set:
            old_values["company"] = visitor.company
            visitor.company = payload.company.strip() or None
            new_values["company"] = visitor.company
        if "visitor_type_id" in fields_set:
            visitor.visitor_type_id = payload.visitor_type_id
        try:
            if actor_id is not None:
                AuditService(self.db).record(actor_user_id=actor_id, action="UPDATE_VISITOR", entity_type="Visitor", entity_id=visitor.id, old_values=old_values, new_values=new_values, **(audit.__dict__ if audit else {}))
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("La identificación ya está registrada.") from exc
        return self.get_visitor(visitor_id)

    def set_active(self, visitor_id: int, active: bool, actor_id: int | None = None, audit: AuditContext | None = None) -> Visitor:
        visitor = self.get_visitor(visitor_id)
        visitor.is_active = active
        if actor_id is not None:
            AuditService(self.db).record(actor_user_id=actor_id, action="UPDATE_VISITOR", entity_type="Visitor", entity_id=visitor_id, old_values={"is_active": not active}, new_values={"is_active": active}, **(audit.__dict__ if audit else {}))
        self.db.commit()
        return self.get_visitor(visitor_id)

    def _validate_visitor_type(self, visitor_type_id: int | None) -> None:
        if visitor_type_id is None:
            return
        visitor_type = self.db.scalar(select(VisitorType).where(VisitorType.id == visitor_type_id))
        if visitor_type is None:
            raise NotFoundError("El tipo de visitante solicitado no existe.")
        if not visitor_type.is_active:
            raise ValidationError("El tipo de visitante solicitado está inactivo.")

    def _ensure_identification_available(self, value: str | None, excluding_id: int | None = None) -> None:
        if value is None:
            return
        query = select(Visitor.id).where(Visitor.identification_normalized == value)
        if excluding_id is not None:
            query = query.where(Visitor.id != excluding_id)
        if self.db.scalar(query) is not None:
            raise ConflictError("La identificación ya está registrada.")
