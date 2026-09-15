from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.application.services.branch_access import BranchContext
from app.infrastructure.persistence.models import Visit


class VisitAccessService:
    """Builds branch-scoped Visit queries from an already authorized context."""

    @staticmethod
    def list_query(context: BranchContext) -> Select[tuple[Visit]]:
        return select(Visit).where(Visit.branch_id == context.branch_id)

    @classmethod
    def list_for_context(cls, db: Session, context: BranchContext) -> list[Visit]:
        return list(db.scalars(cls.list_query(context)).all())
