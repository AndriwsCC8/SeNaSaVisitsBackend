from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.application.services.branch_access import BranchAccessService
from app.infrastructure.persistence.models import (
    Branch,
    Permission,
    Role,
    RolePermission,
    User,
    UserPermission,
    UserRole,
)


@dataclass(frozen=True)
class PermissionEvaluation:
    user_active: bool
    permission_active: bool
    branch_valid: bool
    assignment_valid: bool
    explicit_effects: tuple[str, ...]
    role_granted: bool

    @property
    def allowed(self) -> bool:
        if not self.user_active or not self.permission_active or not self.branch_valid:
            return False
        if "DENY" in self.explicit_effects:
            return False
        if "ALLOW" in self.explicit_effects:
            return self.assignment_valid
        return self.assignment_valid and self.role_granted


class PermissionService:
    """Evaluates effective permissions without trusting client-supplied claims."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def has_permission(
        self,
        user_id: int,
        permission_code: str,
        branch_id: int | None = None,
        at: datetime | None = None,
    ) -> bool:
        evaluated_at = self._utc_naive(at)
        user_active = self.db.scalar(select(User.is_active).where(User.id == user_id))
        permission = self.db.scalar(select(Permission).where(Permission.code == permission_code))
        if user_active is None or permission is None:
            return False
        if user_active is not True or not permission.is_active:
            return False

        if permission.scope == "GLOBAL":
            if branch_id is not None:
                return False
            branch_valid = True
            assignment_valid = True
            explicit_scope = UserPermission.branch_id.is_(None)
        elif permission.scope == "BRANCH":
            if branch_id is None:
                return False
            branch_valid = self.db.scalar(
                select(Branch.is_active).where(Branch.id == branch_id)
            ) is True
            if not branch_valid:
                return False
            assignment_valid = BranchAccessService(self.db).has_current_branch(user_id, branch_id, evaluated_at)
            explicit_scope = UserPermission.branch_id == branch_id
        else:
            return False

        explicit_effects = tuple(
            self.db.scalars(
                select(UserPermission.effect).where(
                    UserPermission.user_id == user_id,
                    UserPermission.permission_id == permission.id,
                    UserPermission.is_active.is_(True),
                    UserPermission.valid_from <= evaluated_at,
                    or_(
                        UserPermission.valid_until.is_(None),
                        UserPermission.valid_until > evaluated_at,
                    ),
                    explicit_scope,
                )
            ).all()
        )
        role_granted = self.db.scalar(
            select(RolePermission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(
                UserRole.user_id == user_id,
                UserRole.is_active.is_(True),
                Role.is_active.is_(True),
                RolePermission.permission_id == permission.id,
                RolePermission.is_active.is_(True),
            )
            .limit(1)
        ) is not None

        return PermissionEvaluation(
            user_active=user_active is True,
            permission_active=permission.is_active,
            branch_valid=branch_valid,
            assignment_valid=assignment_valid,
            explicit_effects=explicit_effects,
            role_granted=role_granted,
        ).allowed

    @staticmethod
    def _utc_naive(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is not None:
            current = current.astimezone(timezone.utc).replace(tzinfo=None)
        return current
