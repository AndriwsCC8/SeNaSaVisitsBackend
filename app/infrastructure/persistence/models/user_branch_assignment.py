from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, NVARCHAR, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from .common import primary_key


class UserBranchAssignment(Base):
    __tablename__ = "user_branch_assignments"
    __table_args__ = (
        CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_assignments_valid_dates"),
        CheckConstraint("(status = 'ACTIVE' AND valid_until IS NULL) OR (status IN ('ENDED', 'CANCELLED') AND valid_until IS NOT NULL)", name="ck_assignments_status_dates"),
        CheckConstraint("status IN ('ACTIVE', 'ENDED', 'CANCELLED')", name="ck_assignments_status"),
        Index("ux_assignments_active_user", "user_id", unique=True, mssql_where="valid_until IS NULL AND status = 'ACTIVE'"),
        Index("ix_assignments_branch_dates", "branch_id", "valid_from", "valid_until"),
        Index("ix_assignments_user_dates", "user_id", "valid_from", "valid_until"),
    )

    id: Mapped[int] = primary_key()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="NO ACTION"), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DATETIME2(precision=3), nullable=True)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"), nullable=False)
    reason: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    status: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME2(precision=3), nullable=False, server_default=text("SYSUTCDATETIME()"), onupdate=text("SYSUTCDATETIME()"))

    user: Mapped[User] = relationship(back_populates="branch_assignments", foreign_keys=[user_id])
    branch: Mapped[Branch] = relationship(back_populates="user_branch_assignments")
    assigned_by: Mapped[User] = relationship(back_populates="assigned_branch_assignments", foreign_keys=[assigned_by_user_id])
