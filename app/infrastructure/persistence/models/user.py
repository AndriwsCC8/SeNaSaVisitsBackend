from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Index, NVARCHAR
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class User(TimestampMixin, Base):
    """Institutional user; local authentication currently requires PasswordHash."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_username", "username", unique=True),
        Index("ix_users_email", "email", unique=True, mssql_where="email IS NOT NULL"),
        Index("ix_users_employee_code", "employee_code", unique=True, mssql_where="employee_code IS NOT NULL"),
    )

    id: Mapped[int] = primary_key()
    username: Mapped[str] = mapped_column(NVARCHAR(80), nullable=False)
    email: Mapped[str | None] = mapped_column(NVARCHAR(254), nullable=True)
    first_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    last_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    employee_code: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    # Keep this non-null until a federated identity provider is explicitly introduced.
    password_hash: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    deactivated_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        foreign_keys="UserRole.user_id",
    )
    assigned_user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="assigned_by",
        foreign_keys="UserRole.assigned_by_user_id",
    )
    assigned_role_permissions: Mapped[list[RolePermission]] = relationship(
        back_populates="assigned_by",
        foreign_keys="RolePermission.assigned_by_user_id",
    )
    user_permissions: Mapped[list[UserPermission]] = relationship(back_populates="user", foreign_keys="UserPermission.user_id")
    assigned_user_permissions: Mapped[list[UserPermission]] = relationship(back_populates="assigned_by", foreign_keys="UserPermission.assigned_by_user_id")
    branch_assignments: Mapped[list[UserBranchAssignment]] = relationship(back_populates="user", foreign_keys="UserBranchAssignment.user_id")
    assigned_branch_assignments: Mapped[list[UserBranchAssignment]] = relationship(back_populates="assigned_by", foreign_keys="UserBranchAssignment.assigned_by_user_id")
    registered_visits: Mapped[list[Visit]] = relationship(back_populates="registered_by", foreign_keys="Visit.registered_by_user_id")
    completed_visits: Mapped[list[Visit]] = relationship(back_populates="completed_by", foreign_keys="Visit.completed_by_user_id")
    cancelled_visits: Mapped[list[Visit]] = relationship(back_populates="cancelled_by", foreign_keys="Visit.cancelled_by_user_id")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor", foreign_keys="AuditLog.actor_user_id")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")
