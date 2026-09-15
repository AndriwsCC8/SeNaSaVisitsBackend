from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Index, NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"
    __table_args__ = (
        Index("ix_permissions_code", "code", unique=True),
        CheckConstraint("scope IN ('BRANCH', 'GLOBAL')", name="ck_permissions_scope"),
    )

    id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(NVARCHAR(80), nullable=False)
    name: Mapped[str] = mapped_column(NVARCHAR(120), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    resource: Mapped[str] = mapped_column(NVARCHAR(80), nullable=False)
    action: Mapped[str] = mapped_column(NVARCHAR(80), nullable=False)
    scope: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    role_permissions: Mapped[list[RolePermission]] = relationship(back_populates="permission")
    user_permissions: Mapped[list[UserPermission]] = relationship(back_populates="permission")
