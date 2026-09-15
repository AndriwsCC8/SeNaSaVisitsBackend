from __future__ import annotations

from sqlalchemy import Boolean, Index, NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import TimestampMixin, primary_key


class Role(TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (Index("ix_roles_code", "code", unique=True),)

    id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    user_roles: Mapped[list[UserRole]] = relationship(back_populates="role")
    role_permissions: Mapped[list[RolePermission]] = relationship(back_populates="role")
