from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, NVARCHAR, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import primary_key


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        Index("ux_user_roles_active", "user_id", "role_id", unique=True, mssql_where="is_active = 1"),
    )

    id: Mapped[int] = primary_key()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="NO ACTION"), nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"))
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"), onupdate=text("SYSUTCDATETIME()"))

    user: Mapped[User] = relationship(back_populates="user_roles", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(back_populates="user_roles")
    assigned_by: Mapped[User] = relationship(back_populates="assigned_user_roles", foreign_keys=[assigned_by_user_id])
