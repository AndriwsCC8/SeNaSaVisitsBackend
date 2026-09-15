from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import primary_key


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        Index("ux_role_permissions_active", "role_id", "permission_id", unique=True, mssql_where="is_active = 1"),
    )

    id: Mapped[int] = primary_key()
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="NO ACTION"), nullable=False)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="NO ACTION"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"))
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    role: Mapped[Role] = relationship(back_populates="role_permissions")
    permission: Mapped[Permission] = relationship(back_populates="role_permissions")
    assigned_by: Mapped[User] = relationship(back_populates="assigned_role_permissions", foreign_keys=[assigned_by_user_id])
