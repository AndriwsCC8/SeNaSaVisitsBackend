from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, NVARCHAR, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import primary_key


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (
        CheckConstraint("effect IN ('ALLOW', 'DENY')", name="ck_user_permissions_effect"),
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_user_permissions_valid_dates"),
        Index("ix_user_permissions_lookup", "user_id", "branch_id", "permission_id", "valid_from", "valid_until"),
    )

    id: Mapped[int] = primary_key()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="NO ACTION"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="NO ACTION"), nullable=True)
    effect: Mapped[str] = mapped_column(NVARCHAR(10), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"))

    user: Mapped[User] = relationship(back_populates="user_permissions", foreign_keys=[user_id])
    permission: Mapped[Permission] = relationship(back_populates="user_permissions")
    branch: Mapped[Branch | None] = relationship(back_populates="user_permissions")
    assigned_by: Mapped[User] = relationship(back_populates="assigned_user_permissions", foreign_keys=[assigned_by_user_id])
