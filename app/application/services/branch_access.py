from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.infrastructure.persistence.models import Branch, UserBranchAssignment

logger = logging.getLogger("senasa_visits.authorization")


@dataclass(frozen=True)
class BranchContext:
    user_id: int
    branch_id: int
    assignment_id: int


class BranchAccessService:
    """Resolves the single current branch context for a user.

    The approved schema has no ``IsActive`` column on assignments; ``Status``
    is the persisted active-state field and must be ``ACTIVE`` here.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current_context(self, user_id: int, at: datetime | None = None) -> BranchContext | None:
        evaluated_at = self._utc_naive(at)
        assignments = list(
            self.db.scalars(
                select(UserBranchAssignment)
                .options(selectinload(UserBranchAssignment.branch))
                .where(
                    UserBranchAssignment.user_id == user_id,
                    UserBranchAssignment.status == "ACTIVE",
                    UserBranchAssignment.valid_from <= evaluated_at,
                    or_(
                        UserBranchAssignment.valid_until.is_(None),
                        UserBranchAssignment.valid_until > evaluated_at,
                    ),
                )
            ).all()
        )

        if len(assignments) != 1:
            if len(assignments) > 1:
                logger.error("Multiple current branch assignments detected for user_id=%s", user_id)
            return None

        assignment = assignments[0]
        branch = assignment.branch
        if branch is None or not branch.is_active:
            return None

        return BranchContext(
            user_id=user_id,
            branch_id=assignment.branch_id,
            assignment_id=assignment.id,
        )

    def has_current_branch(self, user_id: int, branch_id: int, at: datetime | None = None) -> bool:
        context = self.get_current_context(user_id, at)
        return context is not None and context.branch_id == branch_id

    def is_active_branch(self, branch_id: int) -> bool:
        return self.db.scalar(select(Branch.is_active).where(Branch.id == branch_id)) is True

    @staticmethod
    def _utc_naive(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is not None:
            current = current.astimezone(timezone.utc).replace(tzinfo=None)
        return current
