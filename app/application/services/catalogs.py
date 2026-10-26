from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import Branch, BranchType, Role, VisitReason, VisitorType


class CatalogService:
    """Read-only, unpaginated queries for small reference catalogs ordered by name."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_branches(self, *, branch_id: int | None, include_inactive: bool) -> list[Branch]:
        query = select(Branch)
        if branch_id is not None:
            query = query.where(Branch.id == branch_id)
        if not include_inactive:
            query = query.where(Branch.is_active.is_(True))
        return list(self.db.scalars(query.order_by(Branch.name, Branch.id)).all())

    def list_branch_types(self, *, include_inactive: bool) -> list[BranchType]:
        return self._list(BranchType, include_inactive)

    def list_visitor_types(self, *, include_inactive: bool) -> list[VisitorType]:
        return self._list(VisitorType, include_inactive)

    def list_visit_reasons(self, *, include_inactive: bool) -> list[VisitReason]:
        return self._list(VisitReason, include_inactive)

    def list_roles(self) -> list[Role]:
        return self._list(Role, False)

    def _list(self, model, include_inactive: bool) -> list:
        query = select(model)
        if not include_inactive:
            query = query.where(model.is_active.is_(True))
        return list(self.db.scalars(query.order_by(model.name, model.id)).all())
